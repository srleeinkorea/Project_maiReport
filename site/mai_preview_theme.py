"""Compile scoped dark colors for legacy HTML phone previews.
Only presentation declarations are emitted; original rules, markup, scripts and
image pixels stay intact. Scope includes interactive states rendered later.
"""
import re
import colorsys

SCOPE=':where(.phone,.phone *,.mini-phone,.mini-phone *,.device,.device *,body[data-mai-kind="app"] *)'
PREFIX='html[data-mai-theme="dark"][data-mai-theme] body[data-mai-kind] '
COLOR=re.compile(r'#[0-9a-fA-F]{3,8}\b|rgba?\([^()]*\)',re.I)

def rgba(value):
    if value.startswith('#'):
        h=value[1:]
        if len(h) in (3,4):h=''.join(x*2 for x in h)
        if len(h) not in (6,8):return None
        return [int(h[i:i+2],16)/255 for i in (0,2,4)]+[int(h[6:8],16)/255 if len(h)==8 else 1]
    nums=re.findall(r'[\d.]+',value)
    if len(nums) not in (3,4) or '%' in value:return None
    return [float(x)/255 for x in nums[:3]]+[float(nums[3]) if len(nums)==4 else 1]

def recolor(value, role, selector):
    def replace(m):
        v=rgba(m[0])
        if not v:return m[0]
        r,g,b,a=v;h,l,s=colorsys.rgb_to_hls(r,g,b)
        if role=='foreground':
            if l>.78 and s<.15:return m[0] # intentional white on solid CTA
            if s<.20 or (max(r,g,b)-min(r,g,b)<.18 and l<.45):out='#e6edf7' if l<.25 else '#b5c2d6'
            else:
                rgb=colorsys.hls_to_rgb(h,max(.73,l),min(s,.75));out='#'+''.join(f'{round(c*255):02x}' for c in rgb)
        elif role=='border':
            if a<.3:return m[0]
            out='#465976'
        else:
            if l<.3:return m[0] # camera, device frame and dim overlay
            if s>.3 and l<.67:return m[0] # solid semantic/brand fills
            if s>.22:
                rgb=colorsys.hls_to_rgb(h,.19,min(s,.40));out='#'+''.join(f'{round(c*255):02x}' for c in rgb)
            else:out='#192335' if l>.97 else '#222f44'
            if re.search(r'\.(?:app|phone-screen|scroll|phone)\s*$',selector):out='#111827'
        if a<1:
            nums=[int(out[i:i+2],16) for i in (1,3,5)]
            return f'rgba({nums[0]},{nums[1]},{nums[2]},{a:g})'
        return out
    return COLOR.sub(replace,value)

def blocks(css):
    """Walk balanced CSS blocks, retaining media/support conditions."""
    css=re.sub(r'/\*.*?\*/','',css,flags=re.S)
    pos=0
    while pos<len(css):
        start=css.find('{',pos)
        if start<0:return
        prelude=css[pos:start].strip();depth=1;i=start+1;quote=None
        while i<len(css) and depth:
            c=css[i]
            if quote:
                if c==quote and css[i-1]!='\\':quote=None
            elif c in '\"\'':quote=c
            elif c=='{':depth+=1
            elif c=='}':depth-=1
            i+=1
        yield prelude,css[start+1:i-1]
        pos=i

def compile_rules(css):
    out=[]
    for selector,body in blocks(css):
        if selector.startswith('@'):
            if selector.startswith(('@media','@supports')) and 'print' not in selector:
                nested=compile_rules(body)
                if nested:out.append(selector+'{'+nested+'}')
            continue
        # Imports may precede a rule. They are not selectors.
        selector=selector.split(';')[-1].strip()
        if not selector or re.search(r'(^|[ ,])(?:html|body|:root)\b',selector):continue
        # Preserve branded external authentication controls and camera artwork.
        if re.search(r'kakao|km-b|push-ic|shutter|\.prev \.paper|\.cam \.frame',selector):continue
        declarations=[]
        for decl in body.split(';'):
            if ':' not in decl:continue
            prop,value=decl.split(':',1);prop=prop.strip();value=re.sub(r'\s*!important','',value.strip())
            if prop=='color':role='foreground'
            elif prop in ('background','background-color','background-image'):role='background'
            elif prop.startswith('border') and prop not in ('border-radius','border-width','border-style'):role='border'
            else:continue
            text_gradient=role=='background' and bool(re.search(r'background-clip\s*:\s*text',body))
            transformed=recolor(value,'foreground' if text_gradient else role,selector)
            if role=='background':
                transformed=re.sub(r'var\(--(?:ink|ink-1|brand|accent|acc)\)', '#365ee8',transformed)
            if transformed!=value:
                declarations.append(prop+':'+transformed+'!important')
                if text_gradient:declarations.extend(['background-clip:text!important','-webkit-background-clip:text!important'])
        if not declarations:continue
        scoped=[]
        for sel in re.split(r',\s*(?![^()]*\))',selector):
            # Scope the target, including pseudo-elements, without duplicating .phone ancestors.
            pair=sel.strip().split('::',1)
            scoped.append(PREFIX+pair[0]+SCOPE+('::'+pair[1] if len(pair)>1 else ''))
        out.append(','.join(scoped)+'{'+ ';'.join(declarations)+'}')
    return '\n'.join(out)

def preview_theme(html):
    styles=re.findall(r'<style\b[^>]*>(.*?)</style>',html,re.S|re.I)
    return '\n/* Legacy preview component colors (generated, scoped to devices). */\n'+compile_rules('\n'.join(styles))
