"""drawlib - a small writer for editable draw.io method figures (Figure 1 style used by naqid).

Vocabulary: lettered panels with a coloured title bar, gradient and hatched pills, 3-D slabs
(cube), vertical layer bars (vbar), operator circles (op), image stacks of real data (stack,
uri, uri_fig), node graphs, fold strips, thick flow arrows (flow) and a legend row (legend).
Drawing.save() writes the .drawio XML and, if draw.io desktop is installed, exports PNG and
a cropped PDF next to it. Set DRAWIO_EXE if draw.io is not in a standard location.

Dependencies: numpy, Pillow; scipy only for mask contours in uri(); matplotlib only for uri_fig().
"""
import os, io, base64, subprocess, html, shutil
import numpy as np
from PIL import Image

FONT = 'Times New Roman'; INK = '#1F1F1F'; GREY = '#5E5E5E'


def drawio_exe():
    cands = [os.environ.get('DRAWIO_EXE', ''), r'C:/Program Files/draw.io/draw.io.exe',
             '/Applications/draw.io.app/Contents/MacOS/draw.io', shutil.which('drawio') or '',
             shutil.which('draw.io') or '']
    return next((c for c in cands if c and os.path.exists(c)), None)

# pill kinds: fill, gradient, stroke, hatch colour, font colour, bold
PILL = {
    'res': dict(fill='#DDF3FA', grad='#8ED0E6', stroke='#3A8FB0'),
    'pool': dict(fill='#8F7DC9', stroke='#55438F', hatch='#B9ACE3', fc='#FFFFFF', bold=True),
    'up': dict(fill='#FCEBA9', stroke='#B8962E', hatch='#EBA544'),
    'ag': dict(fill='#FDE0C8', grad='#F29E5C', stroke='#C9651F'),
    'seg': dict(fill='#DDF5E3', grad='#7ACD95', stroke='#2E8B57'),
    'cls': dict(fill='#F28A30', grad='#E2701A', stroke='#B9560F', fc='#FFFFFF', bold=True),
    'white': dict(fill='#FFFFFF', stroke='#8A8A8A'),
    'grey': dict(fill='#EDEDED', stroke='#8C8C8C'),
    'bn': dict(fill='#FFFFFF', stroke='#3A8FB0'),
    'wolf': dict(fill='#FFFFFF', stroke='#C9A227'),
    'note': dict(fill='#FFF6E0', stroke='#D9A441'),
}


class Drawing:
    def __init__(self):
        self.cells = []; self._id = 2

    def nid(self):
        self._id += 1; return f'c{self._id}'

    def _cell(self, value, style, x, y, w, h, z=0):
        i = self.nid(); self.cells.append((z, f'<mxCell id="{i}" value="{html.escape(value)}" style="{html.escape(style, quote=True)}" vertex="1" parent="1">'
                                         f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')); return i

    def box(self, x, y, w, h, fill='#FFFFFF', stroke=INK, sw=1.2, dashed=False, arc=10, text='', fs=14, fc=INK, bold=False, italic=False,
            align='center', valign='middle', grad=None, extra=''):
        st = (1 if bold else 0) + (2 if italic else 0)
        s = (f'rounded=1;absoluteArcSize=1;arcSize={arc};whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth={sw};fontFamily={FONT};'
             f'fontSize={fs};fontColor={fc};align={align};verticalAlign={valign};fontStyle={st};spacing=2;' + ('dashed=1;dashPattern=6 4;' if dashed else '')
             + (f'gradientColor={grad};gradientDirection=south;' if grad else '') + extra)
        return self._cell(text, s, x, y, w, h)

    def container(self, x, y, w, h, title, fill, stroke, fs=19, tc=INK, title_h=34):
        self.box(x, y, w, h, fill=fill, stroke=stroke, sw=1.4, arc=22)
        if title: self.label(x + 6, y + 6, w - 12, title_h, title, fs=fs, bold=True, fc=tc)

    def pill(self, x, y, w, h, text, kind='res', fs=14, arc=None, vertical=False, bold=None, sw=1.3):
        p = PILL[kind]; arc = h if arc is None else arc; fc = p.get('fc', INK); b = p.get('bold', False) if bold is None else bold
        ex = 'horizontal=0;' if vertical else ''
        if 'hatch' in p:
            self.box(x, y, w, h, fill=p['fill'], stroke=p['stroke'], sw=sw, arc=arc)
            return self.box(x, y, w, h, fill=p['hatch'], stroke='none', arc=arc, text=text, fs=fs, fc=fc, bold=b, extra='fillStyle=hatch;' + ex)
        return self.box(x, y, w, h, fill=p['fill'], stroke=p['stroke'], sw=sw, arc=arc, text=text, fs=fs, fc=fc, bold=b, grad=p.get('grad'), extra=ex)

    def label(self, x, y, w, h, text, fs=14, fc=INK, bold=False, align='center', italic=False, valign='middle', vertical=False, bg=None):
        st = (1 if bold else 0) + (2 if italic else 0)
        return self._cell(text, f'text;html=1;whiteSpace=wrap;fontFamily={FONT};fontSize={fs};fontColor={fc};align={align};verticalAlign={valign};'
                                f'fontStyle={st};' + ('horizontal=0;' if vertical else '') + (f'fillColor={bg};' if bg else ''), x, y, w, h, z=2 if bg else 0)

    def image(self, x, y, w, h, uri, stroke='none'):
        return self._cell('', f'shape=image;html=1;imageAspect=0;aspect=fixed;image={uri};imageBorder={stroke};strokeWidth=1.5;', x, y, w, h)

    def circle(self, x, y, d, fill, text='', fs=15, fc='#FFFFFF', stroke='none', sw=1.3, bold=True, italic=False):
        i = self.box(x, y, d, d, fill=fill, stroke=stroke, sw=sw, text=text, fs=fs, fc=fc, bold=bold, italic=italic, extra='ellipse;'); self.cells[-1] = (2, self.cells[-1][1]); return i

    def op(self, cx, cy, sym, d=26, fs=16):
        """Operator node centred at (cx, cy): 'C' concatenation, '+' addition, '×' element-wise product."""
        return self.circle(cx - d / 2, cy - d / 2, d, '#FFFFFF', sym, fs=fs, fc=INK, stroke=INK, sw=1.4)

    def dot(self, cx, cy, r=3.5, col=INK):
        self.circle(cx - r, cy - r, 2 * r, col)

    def edge(self, x1, y1, x2, y2, col=INK, sw=1.4, dashed=False, end='block', pts=(), text='', fs=13, start='none', size=6):
        i = self.nid(); s = (f'endArrow={end};startArrow={start};endFill=1;startFill=1;endSize={size};startSize={size};html=1;strokeColor={col};strokeWidth={sw};'
                             f'fontFamily={FONT};fontSize={fs};fontColor={col};' + ('dashed=1;dashPattern=6 4;' if dashed else '') + 'rounded=0;edgeStyle=none;labelBackgroundColor=none;')
        p = ''.join(f'<mxPoint x="{px}" y="{py}"/>' for px, py in pts)
        self.cells.append((1, f'<mxCell id="{i}" value="{html.escape(text)}" style="{html.escape(s, quote=True)}" edge="1" parent="1"><mxGeometry relative="1" as="geometry">'
                          f'<mxPoint x="{x1}" y="{y1}" as="sourcePoint"/><mxPoint x="{x2}" y="{y2}" as="targetPoint"/>' + (f'<Array as="points">{p}</Array>' if p else '') + '</mxGeometry></mxCell>'))

    def save(self, path, width, height, scale=2.5):
        xml = (f'<mxfile host="app.diagrams.net"><diagram id="fig" name="Figure"><mxGraphModel dx="{width}" dy="{height}" grid="0" gridSize="10" guides="1" tooltips="1" '
               f'connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}" background="#FFFFFF" math="0" shadow="0"><root>'
               '<mxCell id="0"/><mxCell id="1" parent="0"/>' + ''.join(c for _, c in sorted(self.cells, key=lambda t: t[0])) + '</root></mxGraphModel></diagram></mxfile>')
        open(path, 'w', encoding='utf-8').write(xml); exe = drawio_exe(); base = os.path.splitext(path)[0]
        if not exe:
            print('draw.io desktop not found: wrote', path, '(set DRAWIO_EXE to export PNG/PDF)'); return
        for fmt, extra in (('png', ['-s', str(scale)]), ('pdf', ['--crop'])):
            subprocess.run([exe, '-x', '-f', fmt, *extra, '-b', '10', '-o', f'{base}.{fmt}', path], capture_output=True, timeout=240)


def uri(path, size=120, mask=None, fill=False, col=(255, 210, 63)):
    """Image (optionally with the expert contour, or the filled binary mask) as a PNG data URI."""
    im = Image.open(path).convert('RGB').resize((size, size), Image.BILINEAR)
    if mask:
        from scipy import ndimage
        m = np.zeros((size, size), bool)
        for mp in (mask if isinstance(mask, list) else [mask]): m |= np.asarray(Image.open(mp).convert('L').resize((size, size), Image.NEAREST)) > 127
        a = np.asarray(im).copy()
        if fill: a[:] = 0; a[m] = (255, 255, 255)
        else: a[m & ~ndimage.binary_erosion(m, iterations=2)] = col
        im = Image.fromarray(a)
    b = io.BytesIO(); im.save(b, 'PNG'); return 'data:image/png,' + base64.b64encode(b.getvalue()).decode()


# ---------------------------------------------------------------- architecture vocabulary (added for the thesis figures)
def _vbar(self, x, y, w, h, fill, stroke, text='', fs=11, fc=INK, arc=4, grad=None, bold=False, sw=1):
    """Narrow vertical layer block with text rotated 90 degrees (as in U-Net figures)."""
    return self.box(x, y, w, h, fill=fill, stroke=stroke, sw=sw, arc=arc, text=text, fs=fs, fc=fc, bold=bold, grad=grad, extra='horizontal=0;')


def _cube(self, x, y, w, h, fill, stroke, size=8, text='', fs=11, fc=INK, sw=1):
    """3-D feature-map slab."""
    s = (f'shape=cube;whiteSpace=wrap;html=1;boundedLbl=1;backgroundOutline=1;darkOpacity=0.08;darkOpacity2=0.18;size={size};fillColor={fill};'
         f'strokeColor={stroke};strokeWidth={sw};fontFamily={FONT};fontSize={fs};fontColor={fc};horizontal=0;')
    return self._cell(text, s, x, y, w, h)


def _tri(self, x, y, w, h, fill, stroke, direction='east', text='', fs=11, fc=INK, sw=1):
    s = f'triangle;whiteSpace=wrap;html=1;fixedSize=1;direction={direction};fillColor={fill};strokeColor={stroke};strokeWidth={sw};fontFamily={FONT};fontSize={fs};fontColor={fc};'
    return self._cell(text, s, x, y, w, h, z=2)


def _stack(self, x, y, w, h, uris, dx=8, dy=8, border='#555555'):
    """Overlapping image stack (back images offset up-right)."""
    n = len(uris)
    for i, u in enumerate(uris):
        off = n - 1 - i; self.image(x + off * dx, y - off * dy, w, h, u, stroke=border)
    return x, y - (n - 1) * dy, w + (n - 1) * dx, h + (n - 1) * dy


def _line(self, x1, y1, x2, y2, col=INK, sw=1.2, dashed=False, pts=()):
    self.edge(x1, y1, x2, y2, col=col, sw=sw, dashed=dashed, end='none', pts=pts)


def _nodes(self, pts, r, fill, stroke, edges=(), ecol='#777777', esw=1.2, dashed_edges=(), dcol='#C0392B', bold_edges=(), bcol='#2E8B57', labels=None, fs=10):
    for (i, j) in edges: self.line(pts[i][0], pts[i][1], pts[j][0], pts[j][1], col=ecol, sw=esw)
    for (i, j) in bold_edges: self.line(pts[i][0], pts[i][1], pts[j][0], pts[j][1], col=bcol, sw=2.6)
    for (i, j) in dashed_edges:
        self.line(pts[i][0], pts[i][1], pts[j][0], pts[j][1], col=dcol, sw=1.6, dashed=True)
        mx, my = (pts[i][0] + pts[j][0]) / 2, (pts[i][1] + pts[j][1]) / 2; self.label(mx - 8, my - 10, 16, 20, '×', fs=15, bold=True, fc=dcol)
    for k, (cx, cy) in enumerate(pts):
        self.circle(cx - r, cy - r, 2 * r, fill, labels[k] if labels else '', fs=fs, fc=INK, stroke=stroke, sw=1.1, bold=False)


def _folds(self, x, y, n=5, w=18, h=14, test=0, val=1, gap=2, tr='#7FB3D5', va='#F5CBA7', te='#34495E'):
    for k in range(n):
        self.box(x + k * (w + gap), y, w, h, fill=te if k == test else va if k == val else tr, stroke='none', arc=2)


def _mask_icon(self, x, y, s=16):
    self.box(x, y, s, s, fill='#000000', stroke='none', arc=0); self.box(x + s * 0.3, y + s * 0.3, s * 0.45, s * 0.4, fill='#FFFFFF', stroke='none', arc=50, extra='ellipse;')


def _panel(self, x, y, w, h, letter, title, col, tint, fs=17, bar=40):
    """Lettered panel: white-tint body, solid coloured title bar, white letter badge."""
    self.box(x, y, w, h, fill=tint, stroke=col, sw=1.8, arc=2)
    self.box(x, y, w, bar, fill=col, stroke=col, sw=1.8, arc=2, text=title, fs=fs, fc='#FFFFFF', bold=True,
             align='left', extra='spacingLeft=50;')
    if letter: self.circle(x + 8, y + 5, bar - 10, '#FFFFFF', letter, fs=fs, fc=col, bold=True)


def _dpanel(self, x, y, w, h, title, col, tint, fs=20):
    """Large dashed pastel panel with a bold-italic title (alternative grammar)."""
    self.box(x, y, w, h, fill=tint, stroke=col, sw=1.8, arc=18, dashed=True)
    self.label(x + 14, y + 6, w - 28, 34, title, fs=fs, fc=col, bold=True, italic=True, align='left')


def _flow(self, x1, y1, x2, y2, col='#22356B', pts=(), dashed=False, sw=3.5):
    """Thick flow arrow between panels."""
    self.edge(x1, y1, x2, y2, col=col, sw=sw, pts=pts, size=8, dashed=dashed)


def _legend(self, x, y, items, fs=15, sw=28, gap=24):
    """Legend row: items = [(kind_or_colour, text), ...]; a kind key of PILL draws a mini pill."""
    cx = x
    for key, text in items:
        if key in PILL:
            self.pill(cx, y, sw * 1.6, 18, '', kind=key)
        else:
            self.box(cx, y, sw * 1.6, 18, fill=key, stroke=key, arc=4)
        tw = 9 * len(text) * fs / 15
        self.label(cx + sw * 1.6 + 6, y - 4, tw, 26, text, fs=fs, align='left')
        cx += sw * 1.6 + 6 + tw + gap
    return cx


def uri_fig(fig, dpi=170):
    """Matplotlib figure -> PNG data URI (for sparklines, heat-maps and curves from real results)."""
    b = io.BytesIO(); fig.savefig(b, format='png', dpi=dpi, bbox_inches='tight', transparent=True)
    import matplotlib.pyplot as plt; plt.close(fig)
    return 'data:image/png,' + base64.b64encode(b.getvalue()).decode()


Drawing.vbar = _vbar; Drawing.cube = _cube; Drawing.tri = _tri; Drawing.stack = _stack; Drawing.line = _line; Drawing.nodes = _nodes
Drawing.folds = _folds; Drawing.mask_icon = _mask_icon
Drawing.panel = _panel; Drawing.dpanel = _dpanel; Drawing.flow = _flow; Drawing.legend = _legend
