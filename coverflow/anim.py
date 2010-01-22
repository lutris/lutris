from math import *

_time = 0

class Animator(object):
    def __init__(self):
        self.dx = 0
        self.dv = 0
    def get(self): pass
    # Arithmetic methods
    def __add__(self, other):
        pass
    def __sub__(self, other):
        pass
    def __mul__(self, other):
        pass
    def __div__(self, other):
        pass
    # Coercion methods
    #def __coerce__(self, other):
    #    return (self.get(), other)
    #def __float__(self):
    #    return float(self.get())
    #def __long__(self):
    #    return long(self.get())
    #def __int__(self):
    #    return int(self.get())
    #def __str__(self):
    #    return str(self.get())

class ConstantAnimator(Animator):
    def __init__(self, val=None):
        super(ConstantAnimator,self).__init__()
        self._val = val
    def set(self, val):
        self._val = val
    def get(self):
        return self._val

# Time handling functions
def constant(t):
    if t < 0: t = 0
    elif t > 1: t = 1
    return t

def extrapolate(t):
    return t

def repeat(t):
    if t >= 1: t = t - int(t)
    elif t < 0: t = 1 + t - int(t)
    return t

def reverse(t):
    if t < 0: t = -t
    if int(t) % 2 == 1: t = 1-(t-int(t))
    else: t = t - int(t)
    return t


# Interpolation functions
def linear(t): return t
def cosine(t): return 1-cos(t*pi/2)
def sine(t): return sin(t*pi/2)
def exponential(t): return (exp(t)-1)/(exp(1)-1)
def ease_out(t): return sqrt(sin(t*pi/2))
def ease_in_elastic(t, a=None, p=None):
    if not p: p = 0.3
    if not a or a < 1.0:
        a = 1.0
        s = p/4.
    else:
        s = p/(2*pi)*asin(1.0/a)
    if t == 0 or t == 1: return t
    return -(a*pow(2,10*(t-1))*sin(((t-1)-s)*(2*pi)/p))
def ease_out_back(t, s=None):
    if not s: s = 1.70158
    t -= 1
    return t*t*((s+1)*t+s)+1
def ease_in_circ(t):
    return 1 - sqrt(1 - t*t)
def ease_out_circ(t):
    t -= 1
    return sqrt(1 - t*t)

class InterpolatedAnimator(Animator):
    def __init__(self, start, end, startt, endt, extend=constant, method=linear):
        super(InterpolatedAnimator,self).__init__()
        self.start = start
        self.end = end
        self.startt = startt
        self.endt = endt
        self.extend = extend
        self.one_over_dt = 1./float(self.endt-self.startt)
        self.set_method(method)
        self.prev_x = 0
    def set_method(self, method, *args):
        self._interpolate = method
        self._args = args
    def set(self, val):
        self.start = self.get()
        self.end = val
        diff = self.endt - self.startt
        self.startt = _time
        self.endt = self.startt + diff
    def get(self):
        t = self.extend((_time-self.startt)*self.one_over_dt)
        x =  (self.end-self.start)*self._interpolate(t, *self._args)+self.start
        self.dx = x - self.prev_x
        self.prev_x = x
        self.dv = self.dx*self.one_over_dt
        return x

class BezierPathAnimator(Animator):
    def __init__(self, p0, p1, p2, p3, startt, endt, extend, method=linear):
        super(BezierPathAnimator,self).__init__()
        self.animator = InterpolatedAnimator(0.0, 1.0, startt, endt, extend=extend, method=method)
        self.p0 = p0
        self.c = 3.0 * (p1 - p0)
        self.b = 3.0 * (p2 - p1) - self.c
        self.a = p3 - p0 - self.c - self.b
        self.prev_x = 0
    def get(self):
        t = self.animator.get()
        t_2 = t*t
        t_3 = t_2*t
        x = self.a*t_3 + self.b*t_2 + self.c*t + self.p0
        self.dx = x - self.prev_x
        self.prev_x = x
        self.dv = self.dx*self.animator.one_over_dt
        return x


_funcs = ["linear", "cosine", "sine", "exponential", "ease_out_back", "ease_in_circ", "ease_out_circ"]
_time_extension = ["constant", "extrapolate", "reverse", "repeat"]

_funcs = dict([(l, globals()[l]) for l in _funcs])
_time_extension = dict([(l, globals()[l]) for l in _time_extension])

#dict(linear=linear,cosine=cosine,sine=sine,exponential=exponential,ease_out_back=ease_out_back,ease_in_circ=ease_in_circ,ease_out_circ=ease_out_circ)

def _handle_time_args(startt, endt, dt):
    if startt is None: startt = _time
    if endt is None:
        if dt is None: raise ValueError("Either dt or endt must be given.")
        endt = startt + dt
    assert startt < endt
    return startt, endt


# ********************************************
# The functions below are exported
#

def set_time(t):
    global _time
    _time = t

def add_time(t):
    global _time
    _time += t
    return _time

class Animatable(object):
    def __init__(self):
        self.anim = ConstantAnimator()
    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.anim: return self.anim.get()
    def __set__(self, obj, value):
        if isinstance(value, Animator):
            self.anim = value
        else: self.anim.set(value)
    def __delete__(self, obj):
        # Free the animator
        del self.anim

def animate(start, end, startt=None, endt=None, dt=None, extend="constant", method="linear"):
    startt, endt = _handle_time_args(startt, endt, dt)
    extend = _time_extension[extend]
    method = _funcs[method]
    try:
        iter(start), iter(end)
    except TypeError:
        return InterpolatedAnimator(start, end, startt, endt, extend, method)
    else:
        return [InterpolatedAnimator(s, e, startt, endt, extend, method)
                for s,e in zip(start, end)]

def bezier3(p0, p1, p2, p3, startt=None, endt=None, dt=None, extend="constant", method="linear"):
    startt, endt = _handle_time_args(startt, endt, dt)
    extend = _time_extension[extend]
    method = _funcs[method]

    try:
        [iter(p) for p in [p0,p1,p2,p3]]
    except TypeError:
        return BezierPathAnimator(p0, p1, p2, p3, startt, endt, extend, method)
    else:
        return [BezierPathAnimator(p0, p1, p2, p3, startt, endt, extend, method)
                for p0, p1, p2, p3 in zip(p0, p1, p2, p3)]

if __name__ == "__main__":
    class Obj(object):
        x = Animatable()
        def __init__(self):
            self.x = 0

    o = Obj()
    add_time(0)
    print o.x   # prints out 0.0
    #o.x.anim = animate("linear", start=5., end=10., dt=5) # this doesn't work
    o.x = animate("linear", start=0, end=1, dt=5)
    add_time(2.5)
    print o.x   # prints out 0.5
    add_time(2.5)
    print o.x # prints out 1.0
    o.x = 10  # Continue the linear interpolation, now from 1 to 10 with a dt of 5
    print o.x # prints out 1.0
    add_time(2.5)
    print o.x # prints out 5.5
    add_time(2.5)
    print o.x # prints out 10.0
    o.x = animate("sine", end=5, dt=5)


