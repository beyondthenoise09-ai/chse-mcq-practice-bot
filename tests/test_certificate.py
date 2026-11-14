import io, unittest
from PIL import Image
from botnex_quiz.certificate import clean_text, render_certificate

BASE = dict(name="Asha Rani", username="asha_k", cls="12th", subject="Physics", chapter="Electric Charges and Fields",
            date="14 Nov 2026", total=50, attempted=48, correct=38, incorrect=10, unattempted=2, marks=38,
            accuracy=79.1666, cert_id="BNX-AB12CD34")

class Cert(unittest.TestCase):
    def png(self, **kw):
        return Image.open(io.BytesIO(render_certificate({**BASE, **kw})))
    def test_renders_png_with_expected_size(self):
        im = self.png(); self.assertEqual(im.format, "PNG"); self.assertEqual(im.size, (2000, 1414))
    def test_unusual_input_never_crashes(self):
        for kw in (dict(name="𝗦 𝗢 𝗟 𝗔 𝗖 𝗘"), dict(name="ଓଡ଼ିଆ नाम", username=""), dict(name=""), dict(name="X" * 200),
                   dict(chapter="W" * 300), dict(total=0, attempted=0, correct=0, incorrect=0, unattempted=0, marks=0, accuracy=0.0),
                   dict(username="")):
            self.assertEqual(self.png(**kw).size, (2000, 1414))
    def test_clean_text(self):
        self.assertEqual(clean_text("𝗦 𝗢 𝗟 𝗔 𝗖 𝗘"), "S O L A C E")
        self.assertEqual(clean_text("ଓଡ଼ିଆ", "Student"), "Student")
    def test_each_render_is_independent(self):
        a = render_certificate(BASE); b = render_certificate({**BASE, "marks": 1, "correct": 1})
        self.assertNotEqual(a, b)
