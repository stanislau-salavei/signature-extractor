"""Screen 2 tools (remarks 5, 6): nothing active by default, toggling, click outside turns the
tool off, crop frame visible but read-only (no handles) without the frame tool.
Pure logic with stand-in objects — no window is created."""
from types import SimpleNamespace

import pytest
from PIL import Image

pv_mod = pytest.importorskip("ui.pages.preview")
pp_mod = pytest.importorskip("ui.pages.process_page")


class FakeButton:
    def __init__(self):
        self.on = False

    def set_on(self, v):
        self.on = v


class FakePreview:
    def __init__(self):
        self.tool = None

    def set_tool(self, t):
        self.tool = t


def make_page():
    page = object.__new__(pp_mod.ProcessPage)
    page.preview = FakePreview()
    page.toolbar = SimpleNamespace(frame=FakeButton(), eraser=FakeButton(), master=None)
    page.c_ink = SimpleNamespace(pick=SimpleNamespace(visible=False))
    page.visible = True
    return page


def test_default_tool_is_none():
    src = open(pv_mod.__file__, encoding="utf-8").read()
    assert 'self.tool = None' in src
    assert 'self.preview.set_tool(None)' in open(pp_mod.__file__, encoding="utf-8").read()


def test_tool_toggles_on_and_off():
    page = make_page()
    page.set_tool("frame")
    assert page.preview.tool == "frame" and page.toolbar.frame.on and not page.toolbar.eraser.on
    page.set_tool("eraser")
    assert page.preview.tool == "eraser" and page.toolbar.eraser.on and not page.toolbar.frame.on
    page.set_tool("eraser")               # second click on the active tool turns it off
    assert page.preview.tool is None and not page.toolbar.eraser.on


def test_click_outside_preview_turns_tool_off():
    page = make_page()
    page.set_tool("eraser")
    inside = SimpleNamespace(master=page.preview)
    page._outside_press(SimpleNamespace(widget=inside))
    assert page.preview.tool == "eraser"
    on_toolbar = SimpleNamespace(master=page.toolbar)
    page._outside_press(SimpleNamespace(widget=on_toolbar))
    assert page.preview.tool == "eraser"
    elsewhere = SimpleNamespace(master=SimpleNamespace(master=None))
    page._outside_press(SimpleNamespace(widget=elsewhere))
    assert page.preview.tool is None and not page.toolbar.eraser.on


def _preview(tool):
    p = object.__new__(pv_mod.Preview)
    p.tool, p.pipette, p.zoom, p.split = tool, False, 1.0, 0.0
    p.drag, p.hover_frame, p.pending_frame = None, False, None
    p.lw, p.lh = 600, 400
    p.app = SimpleNamespace(job=SimpleNamespace(result=SimpleNamespace(frame=(0, 0, 10, 10))))
    p._over_ui = lambda x, y: False
    p.frame_view = lambda: (100.0, 100.0, 300.0, 200.0)
    return p


@pytest.mark.parametrize("tool,expect", [(None, None), ("eraser", ("erase",)), ("frame", ("frame", "l"))])
def test_frame_is_editable_only_with_frame_tool(tool, expect):
    p = _preview(tool)
    assert p._hit(100, 150) == expect      # on the left edge of the frame
    if tool is None:
        assert p._hit(200, 150) is None    # inside: no move either


@pytest.mark.parametrize("tool,handles", [(None, False), ("eraser", False), ("frame", True)])
def test_frame_drawn_always_handles_only_with_tool(tool, handles):
    p = _preview(tool)
    img = Image.new("RGBA", (600, 400), (0, 0, 0, 255))
    p._draw_frame(img)
    px = img.load()
    # dashed outline is visible in every mode
    assert any(px[x, 99] != (0, 0, 0, 255) for x in range(110, 290))
    # white handle squares only with the frame tool
    white = sum(1 for x in range(94, 106) for y in range(94, 106) if px[x, y][:3] == (255, 255, 255))
    assert (white > 10) == handles
