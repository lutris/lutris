try:
    from pyglet.gl import *
    from pyglet import image
except ImportError:
    PYGLET_ENABLED = False
#from PIL import Image
import anim

_glGenTextures = glGenTextures
def glGenTextures(i):
    id = c_uint()
    _glGenTextures(i, byref(id))
    return id.value

_glGetTexLevelParameteriv = glGetTexLevelParameteriv
def glGetTexLevelParameteriv(target, level, pname):
    id = GLint()
    _glGetTexLevelParameteriv(target, level, pname, byref(id))
    return id.value

_glColor4fv = glColor4fv
def glColor4fv(v): _glColor4fv((GLfloat * len(v))(*v))

Z_NEAR = 1.0
Z_FAR  = 50.0
FOVY   = 20.0

width = 0
height = 0
covers = []
pValueCoverTrack = None
pValueCoverAlpha = None
afValues = []

def setup_values():
    global pValueCoverAngle, pValueCoverTrack, pValueCoverAlpha, pValueCoverBounce
    # set some animation variables */
    pValueCoverTrack = anim.animate(start=0, end=0, dt=.5, method="sine")
    pValueCoverAlpha = anim.animate(start=0, end=1., dt=2., method="exponential")

def mk_advance(tracks, covers):
    def advance(reverse=True):
        incr = 0
        if not reverse:
            if not advance.i >= len(tracks)-1: incr = 1
        else:
            if not advance.i <= 0: incr = -1
        advance.i += incr
        covers[advance.i].focus()
        if not incr == 0: covers[advance.i-incr].unfocus(-incr)
        pValueCoverTrack.set(tracks[advance.i])
        return advance.i
    advance.i = 0
    return advance

class Texture:
    def __init__(self, pcFilename):
        self.uiTextureId = glGenTextures(1)
        if (self.uiTextureId == 0): raise Exception()

        # *** load the image using PIL ***
        #picture = Image.open(pcFilename)
        # determine the number of components 
        #iChannels = len(picture.mode)
        # get hold of dimensions and pixel-data
        #self.fWidth, self.fHeight = picture.size
        #pucPixelBuffer = picture.tostring()

        # *** load the image using pyglet ***
        picture = image.load(pcFilename)
        iChannels = len(picture.format)
        self.fWidth, self.fHeight = picture.width, picture.height
        pucPixelBuffer = picture.image_data.data

        self.iTarget = self.what_texture_target(self.fWidth, self.fHeight)


        # *** have pyglet create the texture directly ***
        #texture = picture.texture
        #self.uiTextureId = texture.id
        #self.iTarget = texture.target
        #pucPixelBuffer = texture.image_data.data
        #self.fWidth, self.fHeight = texture.width, texture.height

        self.fMinS = 0.0
        self.fMinT = 0.0
        if self.iTarget == GL_TEXTURE_2D: self.fMaxS, self.fMaxT = 1.0, 1.0
        else: self.fMaxS, self.fMaxT = self.fWidth, self.fHeight

        # see if the texture would fit
        if iChannels == 4: format = GL_RGBA
        else: format = GL_RGB
        if not self.proxy_check(self.iTarget, iChannels, format, int(self.fWidth), int(self.fHeight)):
            print "%s texture won't fit\n"%pcFilename
            glDeleteTextures([self.uiTextureId])
            raise Exception()
        # finally create the GL texture-object
        glBindTexture(self.iTarget, self.uiTextureId)
        glTexParameteri(self.iTarget, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(self.iTarget, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(self.iTarget,
                  0,
                  iChannels,
                  int(self.fWidth), int(self.fHeight),
                  0,
                  format,
                  GL_UNSIGNED_BYTE,
                  pucPixelBuffer)
    def what_texture_target(self, width, height):
        bWidthIsPOT  = False
        bHeightIsPOT = False
        # test width for power-of-two 
        for i in range(32):
            if (width - (1L << (i+1)) == 0):
                bWidthIsPOT = True
                break
        # test height for power-of-two
        for i in range(32):
            if (height - (1L << (i+1)) == 0):
                bHeightIsPOT = True
                break
        # final conclusion */
        if bWidthIsPOT and bHeightIsPOT: return GL_TEXTURE_2D
        else: return GL_TEXTURE_RECTANGLE_ARB

    def proxy_check(self, iTarget, iChannels, iFormat, width, height):
        iProxyTarget = 0
        #iProxyWidth  = 0
        #iProxyHeight = 0
        # select appropriate proxy-target
        if iTarget == GL_TEXTURE_1D:
            iProxyTarget = GL_PROXY_TEXTURE_1D
            glTexImage1D(iProxyTarget,
                         0,
                         iChannels,
                         width,
                         0,
                         iFormat,
                         GL_UNSIGNED_BYTE,
                         None)
        elif iTarget == GL_TEXTURE_2D:
            iProxyTarget = GL_PROXY_TEXTURE_2D
            glTexImage2D (iProxyTarget,
                          0,
                          iChannels,
                          width, height,
                          0,
                          iFormat,
                          GL_UNSIGNED_BYTE,
                          None)
        elif iTarget == GL_TEXTURE_RECTANGLE_ARB:
            iProxyTarget = GL_PROXY_TEXTURE_RECTANGLE_ARB
            glTexImage2D (iProxyTarget,
                          0,
                          iChannels,
                          width, height,
                          0,
                          iFormat,
                          GL_UNSIGNED_BYTE,
                          None)
        # query the results from the proxy-texture-target */
        iProxyWidth = glGetTexLevelParameteriv (iProxyTarget,
                      0,
                      GL_TEXTURE_WIDTH)
        iProxyHeight = glGetTexLevelParameteriv (iProxyTarget,
                      0,
                      GL_TEXTURE_HEIGHT)
        # do the final check if texture would have fitted within the limits
        return (width == iProxyWidth and height == iProxyHeight)

class Cover(object):
    def __init__(self, fSize, pcCoverImage, angle=-70):
        self.pTexture = Texture(pcCoverImage)
        w, h = self.pTexture.fWidth, self.pTexture.fHeight
        if w > h: self.fWidth, self.fHeight = fSize, fSize*float(h)/w
        else: self.fWidth, self.fHeight = fSize*float(w)/h, fSize
        self.angle = angle
        self.z_base = -5
        self.z_focus = -2
        self.y_base = self.fHeight/0.5 - 1
        self.fX = anim.ConstantAnimator(0)
        self.fY = anim.ConstantAnimator(0)
        self.fZ = anim.animate(start=self.z_base, end=self.z_base, dt=.5, method="ease_out_back")
        self.fAngle = anim.animate(start=angle, end=angle, dt=.5, method="ease_out_circ")
        self.fAlpha = pValueCoverAlpha
        self.current = False
    def __del__(self):
        if self.pTexture: del self.pTexture
    def focus(self):
        self.current = True
        self.fAngle.set(0)
        self.fZ.set(self.z_focus)
    def unfocus(self, multiplier=1):
        self.current = False
        self.fAngle.set(self.angle*multiplier)
        self.fZ.set(self.z_base)
    def draw(self):
        fAngle = self.fAngle.get()
        fAlpha = self.fAlpha.get()
        fX = self.fX.get()
        fY = self.fY.get()
        fZ = self.fZ.get()

        # set y-offset of reflection
        fOffset = self.fHeight
        # bind cover-texture
        glBindTexture (self.pTexture.iTarget, self.pTexture.uiTextureId)
        # draw cover and its reflection
        glPushMatrix ()
        glTranslatef(fX, fY, fZ)
        glRotatef(fAngle, 0.0, 1.0, 0.0)
        glBegin(GL_QUADS)

        glColor4f(fAlpha, fAlpha, fAlpha, fAlpha)
        glTexCoord2f(self.pTexture.fMinS, self.pTexture.fMaxT)
        glVertex3f(-self.fWidth / 2.0, -self.fHeight / 2.0, 0.0)
        glTexCoord2f(self.pTexture.fMinS, self.pTexture.fMinT)
        glVertex3f(-self.fWidth / 2.0, self.fHeight / 2.0, 0.0)
        glTexCoord2f(self.pTexture.fMaxS, self.pTexture.fMinT)
        glVertex3f(self.fWidth / 2.0, self.fHeight / 2.0, 0.0)
        glTexCoord2f(self.pTexture.fMaxS, self.pTexture.fMaxT)
        glVertex3f(self.fWidth / 2.0, -self.fHeight / 2.0, 0.0)

        glColor4f(fAlpha, fAlpha, fAlpha, 0.0)
        glTexCoord2f(self.pTexture.fMinS, 0.65 * self.pTexture.fMaxT)
        glVertex3f(-self.fWidth / 2.0,
                -self.fHeight / 2.0 - fOffset + 0.65 * self.fHeight,
                0.0)
        glColor4f(fAlpha, fAlpha, fAlpha, 0.35 * fAlpha)
        glTexCoord2f(self.pTexture.fMinS, self.pTexture.fMaxT)
        glVertex3f(-self.fWidth / 2.0,
                self.fHeight / 2.0 - fOffset,
                0.0)
        glColor4f(fAlpha, fAlpha, fAlpha, 0.35 * fAlpha)
        glTexCoord2f(self.pTexture.fMaxS, self.pTexture.fMaxT)
        glVertex3f(self.fWidth / 2.0,
                self.fHeight / 2.0 - fOffset,
                0.0)
        glColor4f(fAlpha, fAlpha, fAlpha, 0.0)
        glTexCoord2f(self.pTexture.fMaxS, 0.65 * self.pTexture.fMaxT)
        glVertex3f(self.fWidth / 2.0,
                -self.fHeight / 2.0 - fOffset + 0.65 * self.fHeight,
                0.0)
        glEnd()
        glPopMatrix()

def change_projection(bParallel, width, height):
    glMatrixMode (GL_PROJECTION)
    glLoadIdentity ()
    if bParallel:
        glOrtho (-width / 2, width / 2, -height / 2, height / 2, Z_NEAR, Z_FAR)
    else:
        gluPerspective (2.0 * FOVY, float(width) / height, Z_NEAR, Z_FAR)
    glMatrixMode(GL_MODELVIEW)

def display(width, height, covers):
    afBGColor = [0.0, 0.0, 0.0, 1.0]
    # clear background
    fAlpha = 0.5
    clear = afBGColor
    glClearColor(clear[0], clear[1], clear[2], fAlpha)
    glClear(GL_COLOR_BUFFER_BIT)

    # draw covers with perspective projection 
    change_projection(False, width, height);

    glPushMatrix ()
    glTranslatef(-pValueCoverTrack.get(), 0, 0)
    # find the current one
    i = filter(lambda i: covers[i].current, range(len(covers)))[0]
    for cover in covers[:i]:
        cover.draw()
    for cover in covers[:i:-1]:
        cover.draw()
    covers[i].draw()
    glPopMatrix ()

    change_projection(True, width, height)

    # draw left mask
    glDisable(GL_TEXTURE_2D)
    glDisable(GL_TEXTURE_RECTANGLE_ARB)

    glBegin(GL_QUADS)
    fAlpha = 1.0
    
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(-width / 2.0, -height / 2.0)
    fAlpha = 0.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(-width / 2.5, -height / 2.0)
    fAlpha = 0.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f (-width / 2.5, height / 2.0)
    fAlpha = 1.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(-width / 2.0,height / 2.0)
    glEnd()

    # draw right mask 
    glBegin(GL_QUADS)
    fAlpha = 0.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(width / 2.5,-height / 2.0)
    fAlpha = 1.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(width / 2.0,-height / 2.0)
    fAlpha = 1.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(width / 2.0, height / 2.0)
    fAlpha = 0.0
    glColor4f(afBGColor[0], afBGColor[1], afBGColor[2], fAlpha)
    glVertex2f(width / 2.5,height / 2.0)
    glEnd()
    
    glEnable(GL_TEXTURE_2D)
    glEnable(GL_TEXTURE_RECTANGLE_ARB)
