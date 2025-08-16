!pip install gradio

import gradio as gr
import random
import string
import math
from datetime import datetime
from io import StringIO
import tempfile, os

# ---------------- Βοηθητικές Συναρτήσεις ----------------
AMBIGUOUS = set("O0oIl1|S5B8Z2G6Q9")

def build_charset(use_lower, use_upper, use_digits, use_special, avoid_ambiguous):
    charset = ""
    if use_lower:
        charset += string.ascii_lowercase
    if use_upper:
        charset += string.ascii_uppercase
    if use_digits:
        charset += string.digits
    if use_special:
        charset += "".join(ch for ch in string.punctuation if ord(ch) < 128)

    if avoid_ambiguous:
        charset = "".join(ch for ch in charset if ch not in AMBIGUOUS)

    return "".join(sorted(set(charset)))

def ensure_policy(length, opts, charset):
    buckets = []
    if opts["lower"]:
        buckets.append(string.ascii_lowercase)
    if opts["upper"]:
        buckets.append(string.ascii_uppercase)
    if opts["digits"]:
        buckets.append(string.digits)
    if opts["special"]:
        buckets.append("".join(ch for ch in string.punctuation if ord(ch) < 128))

    if opts["avoid_ambiguous"]:
        buckets = [["".join(ch for ch in b if ch not in AMBIGUOUS)] for b in buckets]
        buckets = ["".join(b) for b in buckets]

    buckets = [b for b in buckets if b]

    if not buckets:
        return None

    length = max(length, len(buckets))

    password_chars = [random.choice(b) for b in buckets]
    remaining = length - len(password_chars)
    password_chars += random.choices(charset, k=remaining)
    random.shuffle(password_chars)
    return "".join(password_chars)

def password_entropy_bits(pool_size, length):
    if pool_size <= 1 or length <= 0:
        return 0.0
    return length * math.log2(pool_size)

def entropy_rating(bits):
    if bits < 40:
        return "⚠️ Αδύναμος"
    elif bits < 60:
        return "🟡 Μέτριος"
    elif bits < 80:
        return "🟢 Ισχυρός"
    else:
        return "🟣 Πολύ Ισχυρός"

def render_bar(bits, max_bits=100):
    ratio = max(0.0, min(1.0, bits / max_bits))
    filled = int(ratio * 20)
    return "█" * filled + "░" * (20 - filled)

# ---------------- Πυρήνας Λογικής ----------------
def generate_passwords(length, amount, use_lower, use_upper, use_digits, use_special,
                       avoid_ambiguous, start_with_letter):
    opts = {
        "lower": use_lower,
        "upper": use_upper,
        "digits": use_digits,
        "special": use_special,
        "avoid_ambiguous": avoid_ambiguous
    }

    if not any([use_lower, use_upper, use_digits, use_special]):
        return "⚠️ Επίλεξε τουλάχιστον μία κατηγορία χαρακτήρων.", "", None

    charset = build_charset(use_lower, use_upper, use_digits, use_special, avoid_ambiguous)
    if len(charset) < 4:
        return "⚠️ Το διαθέσιμο αλφάβητο είναι πολύ μικρό.", "", None

    amount = max(1, min(int(amount), 200))
    length = max(4, min(int(length), 128))

    passwords = []
    for _ in range(amount):
        pwd = ensure_policy(length, opts, charset)
        if not pwd:
            return "⚠️ Δεν ήταν δυνατό να ικανοποιηθούν οι περιορισμοί.", "", None

        if start_with_letter:
            letters = ""
            if use_lower:
                letters += string.ascii_lowercase
            if use_upper:
                letters += string.ascii_uppercase
            if avoid_ambiguous:
                letters = "".join(ch for ch in letters if ch not in AMBIGUOUS)
            if letters:
                first = random.choice(letters)
                pwd = first + pwd[1:]
        passwords.append(pwd)

    bits = password_entropy_bits(len(charset), length)
    rating = entropy_rating(bits)
    bar = render_bar(bits)

    md = (
        f"**Ισχύς Κωδικού (εκτίμηση):** {rating}\n\n"
        f"Entropy ≈ `{bits:.1f}` bits  \n"
        f"`{bar}`"
    )

    # γράφουμε σε προσωρινό αρχείο
    sio = StringIO()
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for p in passwords:
        sio.write(p + "\n")
    tmp_path = os.path.join(tempfile.gettempdir(), f"passwords_{timestamp}.txt")
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(sio.getvalue())

    return "\n".join(passwords), md, tmp_path

# ---------------- Gradio UI ----------------
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🔐 Password Generator
    Δημιούργησε ισχυρούς κωδικούς με ρυθμίσεις, έλεγχο ισχύος και εξαγωγή σε αρχείο.
    """)
    with gr.Row():
        with gr.Column():
            length = gr.Slider(4, 64, value=12, step=1, label="Μήκος κωδικού")
            amount = gr.Slider(1, 100, value=5, step=1, label="Πλήθος κωδικών")
            with gr.Row():
                use_lower = gr.Checkbox(value=True, label="πεζά (a–z)")
                use_upper = gr.Checkbox(value=True, label="κεφαλαία (A–Z)")
            with gr.Row():
                use_digits = gr.Checkbox(value=True, label="αριθμοί (0–9)")
                use_special = gr.Checkbox(value=True, label="ειδικοί χαρακτήρες (!@#$...)")
            avoid_ambiguous = gr.Checkbox(value=True, label="Αποφυγή δυσδιάκριτων (O/0, l/1, S/5...)")
            start_with_letter = gr.Checkbox(value=False, label="Να ξεκινάει με γράμμα")
            generate_btn = gr.Button("🎯 Δημιουργία", variant="primary")
        with gr.Column():
            output = gr.Textbox(
                label="Αποτελέσματα",
                lines=8,
                show_copy_button=True,
                placeholder="Οι κωδικοί θα εμφανιστούν εδώ..."
            )
            strength = gr.Markdown("")
            file_out = gr.File(label="Λήψη ως .txt")

    generate_btn.click(
        fn=generate_passwords,
        inputs=[length, amount, use_lower, use_upper, use_digits, use_special,
                avoid_ambiguous, start_with_letter],
        outputs=[output, strength, file_out]
    )

demo.launch(share=True, debug=True)
