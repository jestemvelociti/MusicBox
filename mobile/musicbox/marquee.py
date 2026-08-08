from kivy.clock import Clock
from kivy.core.text import Label as CoreLabel
from kivy.graphics import Color, Rectangle, StencilPop, StencilPush, StencilUnUse, StencilUse
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ColorProperty, NumericProperty, StringProperty
from kivy.uix.widget import Widget

SCROLL_INTERVAL_S = 0.03
SCROLL_STEP_PX = 1
SCROLL_HOLD_S = 1.5


class MarqueeLabel(Widget):
    """Etykieta przewijająca tekst w poziomie, gdy jest szerszy niż widok.

    Gdy tekst się mieści — jest wyśrodkowany. Gdy jest za długi — powoli
    przejeżdża (marquee) z pauzą na końcu, żeby dało się go przeczytać.
    Rysowany ręcznie (bez ScrollView), z clippingiem przez stencil.
    """

    text = StringProperty("")
    bold = BooleanProperty(False)
    text_color = ColorProperty((1, 1, 1, 1))
    font_size = NumericProperty(dp(15))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._cl = None
        self._tw = 0.0
        self._th = 0.0
        self._vmax = 0.0
        self._offset = 0.0
        self._hold = 0.0
        self._timer = None
        self._scrolling = False

        self.bind(
            text=self._rebuild,
            bold=self._rebuild,
            font_size=self._rebuild,
            text_color=self._rebuild,
            size=self._layout_changed,
        )
        self._rebuild()

    def _rebuild(self, *_):
        self._stop()
        self._tw = 0.0
        self._th = 0.0
        try:
            cl = CoreLabel(text=self.text, font_size=self.font_size, bold=self.bold)
            cl.refresh()
            self._cl = cl
            self._tw = float(cl.width)
            self._th = float(cl.height)
        except Exception:
            self._cl = None
        self._offset = 0.0
        self._hold = 0.0
        self._update_scroll()
        self._redraw()

    def _layout_changed(self, *_):
        self._update_scroll()
        self._redraw()

    def _update_scroll(self):
        avail = max(0, self.width)
        self._vmax = max(0.0, self._tw - avail)
        if self._vmax > 1.0 and self._tw > 0 and avail > 0:
            if not self._scrolling:
                self._scrolling = True
                self._timer = Clock.schedule_interval(self._tick, SCROLL_INTERVAL_S)
        else:
            self._stop()

    def _stop(self):
        self._scrolling = False
        self._hold = 0.0
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None

    def _tick(self, _dt):
        if self._vmax <= 1.0:
            self._update_scroll()
            return
        if self._hold > 0:
            self._hold -= SCROLL_INTERVAL_S
            return
        self._offset = min(self._vmax, self._offset + SCROLL_STEP_PX)
        if self._offset >= self._vmax:
            self._hold = SCROLL_HOLD_S
            self._offset = self._vmax
        self._redraw()

    def _redraw(self):
        self.canvas.clear()
        if self._cl is None or self._tw <= 0 or self.width <= 0 or self.height <= 0:
            return
        tex = self._cl.texture
        if tex is None:
            return
        tex_w, tex_h = tex.size
        r, g, b, a = self.text_color
        with self.canvas:
            StencilPush()
            Color(1, 1, 1, 1)
            Rectangle(pos=self.pos, size=self.size)
            StencilUse()
            Color(r, g, b, a)
            if self._tw <= self.width:
                x = self.x + (self.width - tex_w) / 2.0
            else:
                x = self.x - self._offset
            y = self.y + (self.height - tex_h) / 2.0
            Rectangle(texture=tex, pos=(x, y), size=(tex_w, tex_h))
            StencilUnUse()
            StencilPop()
