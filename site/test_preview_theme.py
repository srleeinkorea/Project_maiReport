"""Regression checks for preview color compilation (stdlib only)."""
import unittest
from mai_preview_theme import preview_theme,recolor

class PreviewThemeTests(unittest.TestCase):
    def test_neutral_roles_and_camera_overlay(self):
        self.assertEqual(recolor('#fff','background','.card'),'#192335')
        self.assertEqual(recolor('#111827','foreground','.title'),'#e6edf7')
        self.assertEqual(recolor('rgba(16,21,31,.45)','background','.dim'),'rgba(16,21,31,.45)')

    def test_states_pseudoelements_and_responsive_scope(self):
        css=preview_theme('<style>@media(max-width:500px){.phone .card:hover{background:#fff}}.phone .card::before{color:#111827}</style>')
        self.assertIn('@media(max-width:500px)',css)
        self.assertIn(':hover:where(',css)
        self.assertIn('*)::before',css)
        self.assertIn('html[data-mai-theme="dark"]',css)
        self.assertNotIn('width:',css.replace('max-width:',''))

    def test_gradient_text_keeps_clipping(self):
        css=preview_theme('<style>.lab{background:linear-gradient(#2f6bff,#7c5cfc);background-clip:text;color:transparent}</style>')
        self.assertIn('background-clip:text!important',css)
        self.assertIn('-webkit-background-clip:text!important',css)

    def test_print_layout_scripts_and_brand_are_untouched(self):
        css=preview_theme('<style>@media print{.phone{background:#fff}}.bi-kakao{background:#fee500;color:#191919}.phone{width:400px}</style><script>secret()</script>')
        self.assertNotIn('print',css)
        self.assertNotIn('bi-kakao',css)
        self.assertNotIn('400',css)
        self.assertNotIn('secret',css)

if __name__=='__main__':unittest.main()
