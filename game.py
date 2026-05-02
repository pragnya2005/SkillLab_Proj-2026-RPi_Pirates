import pygame
import time
import random
import math
from server.server import get_inputs

WIDTH, HEIGHT = 800, 600
WIN_SCORE = 5

# ── Colour palette ──────────────────────────────────────────────────────────
BG_DARK   = (10, 10, 30)
BG_BLACK  = (0,  0,  0)
WHITE     = (255, 255, 255)
YELLOW    = (255, 220, 0)
CYAN      = (0,  200, 255)
PINK      = (255,  60, 120)
GREEN     = (0,  255, 120)
ORANGE    = (255, 140,  0)
PURPLE    = (180,  80, 255)
DIM       = (120, 120, 140)
P1_COL    = (0,  150, 255)
P2_COL    = (255,  80,  80)

POWER_COLORS = {
    "BIG":     (0,   255, 120),
    "SLOW":    (0,   180, 255),
    "INVIS":   (200,  80, 255),
    "FAST":    (255, 120,   0),
    "DOUBLE":  (255, 255,   0),
    "REVERSE": (255,   0, 120),
}
POWER_LABELS = {
    "BIG":"B","SLOW":"S","INVIS":"I",
    "FAST":"F","DOUBLE":"2","REVERSE":"R"
}
POWER_DESCS = {
    "BIG":     "BIG PADDLE",
    "SLOW":    "SLOW BALL",
    "INVIS":   "INVISIBLE BALL",
    "FAST":    "FAST BALL",
    "DOUBLE":  "DOUBLE BALL",
    "REVERSE": "REVERSE CONTROLS",
}

# ── Star particle ────────────────────────────────────────────────────────────
class Star:
    def __init__(self):
        self.reset(random.randint(0, WIDTH), random.randint(0, HEIGHT))

    def reset(self, x=None, y=None):
        self.x = x if x is not None else random.randint(0, WIDTH)
        self.y = y if y is not None else 0
        self.speed = random.uniform(0.2, 0.8)
        self.size  = random.choice([1, 1, 1, 2])
        self.bright = random.randint(100, 255)
        self.phase  = random.uniform(0, math.pi * 2)

    def update(self):
        self.y += self.speed
        if self.y > HEIGHT:
            self.reset()

    def draw(self, surf):
        twinkle = int(self.bright * (0.6 + 0.4 * math.sin(time.time() * 2 + self.phase)))
        c = (twinkle, twinkle, min(255, twinkle + 40))
        pygame.draw.rect(surf, c, (int(self.x), int(self.y), self.size, self.size))


class PongGame:
    def __init__(self):
        pygame.init()
        pygame.mixer.init()

        self.fullscreen   = False
        self.base_surface = pygame.Surface((WIDTH, HEIGHT))
        self.screen       = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("Ping Pong")

        self.clock = pygame.time.Clock()

        self.font_path = "assets/pixel.ttf"
        self._font_cache = {}

        self.win_sound = pygame.mixer.Sound("assets/win.wav")

        # ── stars ──
        self.stars = [Star() for _ in range(80)]

        # ── cursor blink ──
        self.blink_t = time.time()
        self.blink_on = True

        self.reset_all()

    # ── font helper ─────────────────────────────────────────────────────────
    def font(self, size):
        if size not in self._font_cache:
            self._font_cache[size] = pygame.font.Font(self.font_path, size)
        return self._font_cache[size]

    def render_fit(self, text, maxw, size):
        while size > 10:
            s = self.font(size).render(text, True, WHITE)
            if s.get_width() <= maxw:
                return s
            size -= 2
        return s

    # ── full reset ──────────────────────────────────────────────────────────
    def reset_all(self):
        self.left  = pygame.Rect(20, HEIGHT // 2 - 50, 10, 100)
        self.right = pygame.Rect(WIDTH - 30, HEIGHT // 2 - 50, 10, 100)

        self.ball  = pygame.Rect(WIDTH // 2, HEIGHT // 2, 15, 15)
        self.speed = [5, 5]

        self.s1 = 0
        self.s2 = 0

        self.name1      = ""
        self.name2      = ""
        self.input_text = ""
        self.input_prompt = ""

        self.state   = "WELCOME"
        self.mode    = None
        self.submode = None

        self.count_start = 0
        self.paused      = False

        # AI
        self.ai_speed = 5
        self.ai_error = 25
        self.ai_miss = 0.05

        # Powerups
        self.powerup      = None
        self.power_type   = None
        self.power_start  = 0
        self.power_active = False
        self.power_timer  = 5       # seconds each powerup lasts

        self.ball_visible = True
        self.reverse      = False
        self.extra_ball   = None
        self.extra_speed  = [0, 0]
        self.last_spawn   = time.time()

        # menu selected index
        self.menu_sel = 0

        # winner
        self.winner = ""

    # ── star background ──────────────────────────────────────────────────────
    def draw_stars(self):
        self.base_surface.fill(BG_DARK)
        for s in self.stars:
            s.update()
            s.draw(self.base_surface)

    # ── generic menu helpers ─────────────────────────────────────────────────
    def draw_title_bar(self, line1, line2=None, y1=60, y2=110):
        """Draw a two-line title at top."""
        s1 = self.font(50).render(line1, True, YELLOW)
        self.base_surface.blit(s1, s1.get_rect(centerx=WIDTH // 2, top=y1))
        if line2:
            s2 = self.font(36).render(line2, True, CYAN)
            self.base_surface.blit(s2, s2.get_rect(centerx=WIDTH // 2, top=y2))

    def draw_menu_items(self, items, start_y=200, gap=64, selected=-1):
        """
        items: list of (key_label, text) e.g. ("1", "COMPUTER")
        selected: index of highlighted item (-1 = none)
        """
        for i, (key, label) in enumerate(items):
            y = start_y + i * gap
            is_sel = (i == selected)

            # highlight box
            if is_sel:
                box = pygame.Rect(WIDTH // 2 - 220, y - 8, 450, 52)
                pygame.draw.rect(self.base_surface, (30, 30, 70), box, border_radius=10)
                pygame.draw.rect(self.base_surface, CYAN, box, 2, border_radius=10)

            # key badge
            badge_col = YELLOW if not is_sel else CYAN
            key_surf = self.font(22).render(key, True, BG_BLACK)
            badge_rect = pygame.Rect(WIDTH // 2 - 185, y, 34, 34)
            pygame.draw.rect(self.base_surface, badge_col, badge_rect, border_radius=6)
            self.base_surface.blit(key_surf, key_surf.get_rect(center=badge_rect.center))

            # label
            col = WHITE if not is_sel else YELLOW
            lbl_surf = self.font(28).render(label, True, col)
            self.base_surface.blit(lbl_surf, (WIDTH // 2 - 138, y + 3))

            # arrow
            #if is_sel:
             #   arr = self.font(28).render("▶", True, CYAN)
              #  self.base_surface.blit(arr, (WIDTH // 2 + 10, y + 3))

    def draw_divider(self):
        pygame.draw.line(self.base_surface, (50, 50, 80), (WIDTH // 2 - 160, 170), (WIDTH // 2 + 160, 170), 1)

    def draw_hint(self, text, y=HEIGHT - 40):
        s = self.font(16).render(text, True, DIM)
        self.base_surface.blit(s, s.get_rect(centerx=WIDTH // 2, centery=y))

    def draw_credits(self):
        s = self.font(14).render("Created by RPi-Pirates", True, DIM)
        self.base_surface.blit(s, s.get_rect(right=WIDTH - 16, bottom=HEIGHT - 12))

    # ── WELCOME screen ───────────────────────────────────────────────────────
    def draw_welcome(self):
        self.draw_stars()

        # glow ring behind title
        cx, cy = WIDTH // 2, 130
        for r in range(90, 20, -10):
            alpha = int(30 * (90 - r) / 70)
            glow = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
            pygame.draw.circle(glow, (0, 180, 255, alpha), (r, r), r)
            self.base_surface.blit(glow, (cx - r, cy - r))

        t1 = self.font(32).render("WELCOME TO", True, WHITE)
        t2 = self.font(60).render("PING PONG", True, YELLOW)
        # shadow
        t2s = self.font(60).render("PING PONG", True, (120, 80, 0))
        self.base_surface.blit(t2s, t2s.get_rect(centerx=WIDTH // 2 + 3, centery=130 + 3))
        self.base_surface.blit(t1, t1.get_rect(centerx=WIDTH // 2, centery=70))
        self.base_surface.blit(t2, t2.get_rect(centerx=WIDTH // 2, centery=140))

        # ping pong emoji-ish pixel paddle + ball graphic
        pygame.draw.rect(self.base_surface, P1_COL,    (WIDTH // 2 - 100, 200, 8, 60),  border_radius=3)
        pygame.draw.rect(self.base_surface, P2_COL,    (WIDTH // 2 + 92,  200, 8, 60),  border_radius=3)
        pygame.draw.ellipse(self.base_surface, WHITE,  (WIDTH // 2 - 8,   224, 16, 16))

        # press any key
        pulse = int(200 + 55 * math.sin(time.time() * 3))
        pak = self.font(22).render("PRESS ANY KEY TO START", True, (pulse, pulse, pulse))
        self.base_surface.blit(pak, pak.get_rect(centerx=WIDTH // 2, centery=340))

        self.draw_credits()

    # ── MAIN menu ────────────────────────────────────────────────────────────
    def draw_main(self):
        self.draw_stars()
        self.draw_title_bar("PING PONG", "SELECT MODE")
        self.draw_divider()
        self.draw_menu_items([
            ("1", "SINGLE PLAYER"),
            ("2", "MULTI PLAYER "),
        ], selected=self.menu_sel)
        self.draw_hint("↑↓ or 1/2 to select  •  ENTER to confirm")
        self.draw_credits()

    # ── LEVEL select ─────────────────────────────────────────────────────────
    def draw_level(self):
        self.draw_stars()
        self.draw_title_bar("DIFFICULTY", "HOW TOUGH?")
        self.draw_divider()

        items = [("1","EASY"),("2","MEDIUM"),("3","HARD")]

        for i,(key,label) in enumerate(items):
            y = 200 + i*64
            is_sel = (i == self.menu_sel)

            # COLORS
            if i == 0:
                col = (0,255,120) if is_sel else WHITE   # GREEN
            elif i == 1:
                col = (255,220,0) if is_sel else WHITE   # YELLOW
            else:
                col = (255,80,80) if is_sel else WHITE   # RED

            txt = self.font(28).render(f"{key} {label}", True, col)
            rect = txt.get_rect(center=(WIDTH//2, y))
            self.base_surface.blit(txt, rect)

            if is_sel:
                box = pygame.Rect(WIDTH//2-200, y-25, 400, 50)
                pygame.draw.rect(self.base_surface,(30,30,70),box, border_radius=10)
                pygame.draw.rect(self.base_surface, col, box,2,border_radius=10)

                self.base_surface.blit(txt, rect)

        self.draw_hint("↑↓ or 1/2/3 • ENTER")
        self.draw_credits()

    # ── MODE SELECT ──────────────────────────────────────────────────────────
    def draw_mode_select(self):
        self.draw_stars()
        self.draw_title_bar("CONTROLS", "HOW WILL YOU PLAY?")
        self.draw_divider()
        self.draw_menu_items([
            ("1", "KEYBOARD"),
            ("2", "PHONE "),
        ], selected=self.menu_sel)
        self.draw_hint("↑↓ or 1/2 to select  •  ENTER to confirm")
        self.draw_credits()

    # ── NAME entry ───────────────────────────────────────────────────────────
    def draw_name(self):
        self.draw_stars()

        prompt = self.input_prompt or "ENTER YOUR NAME"
        t = self.font(36).render(prompt, True, YELLOW)
        self.base_surface.blit(t, t.get_rect(centerx=WIDTH // 2, centery=200))

        # input box
        box = pygame.Rect(WIDTH // 2 - 220, 260, 440, 60)
        pygame.draw.rect(self.base_surface, (20, 20, 50), box, border_radius=10)
        pygame.draw.rect(self.base_surface, CYAN, box, 2, border_radius=10)

        # blink cursor
        if time.time() - self.blink_t > 0.5:
            self.blink_on = not self.blink_on
            self.blink_t  = time.time()
        display = self.input_text + ("_" if self.blink_on else " ")

        name_surf = self.render_fit(display, 400, 36)
        self.base_surface.blit(name_surf, name_surf.get_rect(centerx=WIDTH // 2, centery=290))

        self.draw_hint("ENTER to confirm  •  BACKSPACE to delete")
        self.draw_credits()

    # ── HELP screen ──────────────────────────────────────────────────────────
    def draw_help(self):
        self.draw_stars()

        title = self.font(40).render("POWER-UPS", True, YELLOW)
        self.base_surface.blit(title, title.get_rect(centerx=WIDTH // 2, centery=44))

        pygame.draw.line(self.base_surface, (80, 80, 120), (60, 72), (WIDTH - 60, 72), 1)

        powerups = [
            ("B", "BIG",     "BIG PADDLE",  "larger paddle-5s"),
            ("S", "SLOW",    "SLOW BALL",   "speed reduced-5s"),
            ("I", "INVIS",   "INVISIBLE",   "ball hides-5s"),
            ("F", "FAST",    "FAST BALL",   "speed boosted-5s"),
            ("2", "DOUBLE",  "DOUBLE BALL", "two balls-5s"),
            ("R", "REVERSE", "REVERSE",     "controls flipped-5s"),
        ]

        row_h = 72
        for idx, (lbl, key, name, detail) in enumerate(powerups):
            col = POWER_COLORS[key]
            y   = 85 + idx * row_h

            # coloured badge
            badge = pygame.Rect(48, y+6, 40, 40)
            pygame.draw.rect(self.base_surface, col, badge, border_radius=8)
            pygame.draw.rect(self.base_surface, WHITE, badge, 1, border_radius=8)
            ls = self.font(24).render(lbl, True, BG_BLACK)
            self.base_surface.blit(ls, ls.get_rect(center=badge.center))

            # name bold
            ns = self.font(20).render(name, True, col)
            self.base_surface.blit(ns, (106, y + 6))

            # detail smaller, dimmed
            ds = self.font(16).render(detail, True, DIM)
            self.base_surface.blit(ds, (106, y + 30))

        # controls hint box
        hint_box = pygame.Rect(10, HEIGHT - 74, WIDTH - 20, 50)
        pygame.draw.rect(self.base_surface, (20, 20, 50), hint_box, border_radius=8)
        pygame.draw.rect(self.base_surface, (60, 60, 100), hint_box, 1, border_radius=8)

        hints = [
            ("Ctrl+H", "Help"), ("P", "Pause"), ("Ctrl+F", "Fullscreen"),
            ("Ctrl+M", "Menu"), ("↑↓", "Move"),
        ]
        hx = 26
        for key, label in hints:
            ks = self.font(12).render(key, True, YELLOW)
            ls = self.font(12).render(f" {label}", True, DIM)
            self.base_surface.blit(ks, (hx, HEIGHT - 58))
            self.base_surface.blit(ls, (hx + ks.get_width(), HEIGHT - 58))
            hx += ks.get_width() + ls.get_width() + 8

        pak = self.font(16).render("PRESS ANY KEY TO CONTINUE", True, CYAN)
        self.base_surface.blit(pak, pak.get_rect(centerx=WIDTH // 2, centery=HEIGHT - 85))

    # ── GAME arena ───────────────────────────────────────────────────────────
    def draw_game(self):
        self.base_surface.fill(BG_DARK)

        # ── dashed centre line ──
        for y in range(0, HEIGHT, 20):
            pygame.draw.line(self.base_surface, (60, 60, 90), (WIDTH // 2, y), (WIDTH // 2, y + 10), 2)

        # ── paddles ──
        pygame.draw.rect(self.base_surface, P1_COL, self.left,  border_radius=4)
        pygame.draw.rect(self.base_surface, P2_COL, self.right, border_radius=4)

        # ── ball ──
        if self.ball_visible:
            pygame.draw.ellipse(self.base_surface, WHITE, self.ball)

        if self.extra_ball:
            pygame.draw.ellipse(self.base_surface, YELLOW, self.extra_ball)

        # ── scoreboard — split across centre line ──
        n1 = self.name1 or "P1"
        n2 = self.name2 or "P2"

        # scores large, anchored to centre line
        sc1 = self.font(52).render(str(self.s1), True, P1_COL)
        sc2 = self.font(52).render(str(self.s2), True, P2_COL)
        self.base_surface.blit(sc1, sc1.get_rect(right=WIDTH // 2 - 24, top=8))
        self.base_surface.blit(sc2, sc2.get_rect(left=WIDTH // 2 + 24,  top=8))

        # names smaller, just outside scores
        nm1 = self.render_fit(n1, 280, 20)
        nm2 = self.render_fit(n2, 280, 20)
        self.base_surface.blit(nm1, nm1.get_rect(right=WIDTH // 2 - 24, top=66))
        self.base_surface.blit(nm2, nm2.get_rect(left=WIDTH // 2 + 24,  top=66))

        # separator |
        sep = self.font(52).render("|", True, (60, 60, 90))
        self.base_surface.blit(sep, sep.get_rect(centerx=WIDTH // 2, top=8))

        # ── active powerup HUD ──
        self._draw_powerup_hud()

        # ── spawned powerup on field ──
        if self.powerup:
            col = POWER_COLORS[self.power_type]
            pygame.draw.rect(self.base_surface, col, self.powerup, border_radius=6)
            pygame.draw.rect(self.base_surface, WHITE, self.powerup, 1, border_radius=6)
            ls = self.font(16).render(POWER_LABELS[self.power_type], True, BG_BLACK)
            self.base_surface.blit(ls, ls.get_rect(center=self.powerup.center))

        # ── pause hint ──
        hint = self.font(14).render("P Pause  H Help  ESC Home", True, (60, 60, 90))
        self.base_surface.blit(hint, hint.get_rect(centerx=WIDTH // 2, bottom=HEIGHT - 4))

        # ── fullscreen X button ──
        if self.fullscreen:
            self._draw_close_btn()

    def _draw_powerup_hud(self):
        """Strip of all powerup icons bottom-right, active one highlighted + timer bar."""
        icons = list(POWER_COLORS.keys())
        icon_size = 32
        pad = 6
        total_w = len(icons) * (icon_size + pad) - pad
        sx = WIDTH - total_w - 16
        sy = HEIGHT - icon_size - 28

        for i, key in enumerate(icons):
            x = sx + i * (icon_size + pad)
            col = POWER_COLORS[key]
            is_active = self.power_active and self.power_type == key

            if is_active:
                # glow border
                glow_rect = pygame.Rect(x - 2, sy - 2, icon_size + 4, icon_size + 4)
                pygame.draw.rect(self.base_surface, col, glow_rect, border_radius=8)
            else:
                dim_col = tuple(c // 4 for c in col)
                pygame.draw.rect(self.base_surface, dim_col, (x, sy, icon_size, icon_size), border_radius=6)
                pygame.draw.rect(self.base_surface, (20, 40, 60), (x, sy, icon_size, icon_size), 1, border_radius=6)

            ls = self.font(16).render(POWER_LABELS[key], True, BG_BLACK if is_active else (80, 80, 100))
            self.base_surface.blit(ls, ls.get_rect(center=(x + icon_size // 2, sy + icon_size // 2)))

            # timer bar under active icon
            if is_active:
                elapsed  = time.time() - self.power_start
                fraction = max(0, 1 - elapsed / self.power_timer)
                bar_w    = int(icon_size * fraction)
                pygame.draw.rect(self.base_surface, (40, 40, 60),   (x, sy + icon_size + 2, icon_size, 4))
                pygame.draw.rect(self.base_surface, col,            (x, sy + icon_size + 2, bar_w, 4))

    def _draw_close_btn(self):
        """Small X button in top-right corner for fullscreen exit."""
        rect = pygame.Rect(WIDTH - 44, 8, 36, 36)
        pygame.draw.rect(self.base_surface, (60, 20, 20), rect, border_radius=6)
        pygame.draw.rect(self.base_surface, PINK, rect, 1, border_radius=6)
        xs = self.font(22).render("✕", True, PINK)
        self.base_surface.blit(xs, xs.get_rect(center=rect.center))
        return rect

    # ── PAUSE overlay ────────────────────────────────────────────────────────
    def draw_pause(self):
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 140))
        self.base_surface.blit(overlay, (0, 0))

        box = pygame.Rect(WIDTH // 2 - 160, HEIGHT // 2 - 70, 320, 140)
        pygame.draw.rect(self.base_surface, (20, 20, 50), box, border_radius=14)
        pygame.draw.rect(self.base_surface, CYAN, box, 2, border_radius=14)

        pt = self.font(42).render("PAUSED", True, YELLOW)
        self.base_surface.blit(pt, pt.get_rect(centerx=WIDTH // 2, centery=HEIGHT // 2 - 20))
        rect = pygame.Rect(WIDTH//2 - 400, HEIGHT//2 + 20, 800, 30)
        ph = self.font(16).render("P resume • ESC home", True, DIM)
        self.base_surface.blit(ph, ph.get_rect(center=rect.center))
        #self.base_surface.blit(ph, ph.get_rect(centerx=WIDTH // 2, centery=HEIGHT // 2 + 44))

    # ── COUNTDOWN ────────────────────────────────────────────────────────────
    def countdown(self):
        self.draw_game()
        t   = time.time() - self.count_start
        num = None
        if   t < 1: num = "3"
        elif t < 2: num = "2"
        elif t < 3: num = "1"
        elif t < 4: num = "GO!"
        else:
            self.state = "PLAY"
            return

        pulse = 1.0 + 0.15 * math.sin(time.time() * 20)
        size  = int(80 * pulse)
        col   = YELLOW if num != "GO!" else GREEN
        ns    = self.font(size).render(num, True, col)
        self.base_surface.blit(ns, ns.get_rect(center=(WIDTH // 2, HEIGHT // 2)))

    # ── WINNER screen ────────────────────────────────────────────────────────
    def draw_winner(self):
        self.draw_stars()

        trophy = self.font(60).render("🏆", True, YELLOW)   # may not render in pixel font; fallback
        self.base_surface.blit(trophy, trophy.get_rect(centerx=WIDTH // 2, centery=130))

        wt = self.render_fit(f"{self.winner} WINS!", WIDTH - 40, 52)
        wt_col = self.font(52).render("", True, YELLOW)   # just for size ref
        # colour pass
        wt2 = self.render_fit(f"{self.winner} WINS!", WIDTH - 40, 52)
        # draw with glow
        sh = self.render_fit(f"{self.winner} WINS!", WIDTH - 40, 52)
        shc = pygame.Surface(sh.get_size(), pygame.SRCALPHA)
        shc.blit(sh, (0, 0))
        shc.set_alpha(80)
        self.base_surface.blit(shc, shc.get_rect(centerx=WIDTH // 2 + 3, centery=245))
        self.base_surface.blit(wt, wt.get_rect(centerx=WIDTH // 2, centery=239))

        # scores
        sc = self.font(25).render(f"{self.s1}     :     {self.s2}", True, WHITE)
        self.base_surface.blit(sc, sc.get_rect(centerx=WIDTH // 2, centery=310))

        n1 = self.render_fit(self.name1 or "P1", 200, 20)
        n2 = self.render_fit(self.name2 or "P2", 200, 20)
        self.base_surface.blit(n1, n1.get_rect(right=WIDTH // 2 - 24, centery=310))
        self.base_surface.blit(n2, n2.get_rect(left=WIDTH // 2 + 24,  centery=310))

        # Play again button
        pulse = int(200 + 55 * math.sin(time.time() * 3))
        pa = self.font(26).render("PRESS  Y  TO  PLAY  AGAIN", True, (pulse, pulse, 0))
        self.base_surface.blit(pa, pa.get_rect(centerx=WIDTH // 2, centery=400))

        self.draw_hint("ESC to return home", HEIGHT - 40)
        self.draw_credits()

    # ── paddle movement ──────────────────────────────────────────────────────
    def move_keyboard(self, keys):
        factor = -1 if self.reverse else 1
        if keys[pygame.K_w]: self.left.y -= 6 * factor
        if keys[pygame.K_s]: self.left.y += 6 * factor
        if self.submode == "KEYBOARD":
            if keys[pygame.K_UP]:   self.right.y -= 6 * factor
            if keys[pygame.K_DOWN]: self.right.y += 6 * factor

    def move_phone(self):
        data   = get_inputs()
        factor = -1 if self.reverse else 1
        self.left.y  += int(data["p1"]["y"] * 10 * factor)
        self.right.y += int(data["p2"]["y"] * 10 * factor)

    def move_ai(self):
        target = self.ball.centery
        if self.ball.right >= WIDTH * 0.6 and random.random() < self.ai_miss:
            miss_amount = self.ai_error + random.randint(60, 100)
            target += miss_amount * random.choice((-1, 1))
        else:
            target += random.randint(-self.ai_error, self.ai_error)

        if self.right.centery < target:
            self.right.y += self.ai_speed
        else:
            self.right.y -= self.ai_speed

    # ── powerup logic ────────────────────────────────────────────────────────
    def spawn_power(self):
        if self.mode != "MULTI": return
        if not self.powerup and time.time() - self.last_spawn > 6:
            self.powerup    = pygame.Rect(random.randint(200, 600), random.randint(100, 500), 28, 28)
            self.power_type = random.choice(list(POWER_COLORS.keys()))
            self.last_spawn = time.time()

    def activate_power(self):
        self.power_active = True
        self.power_start  = time.time()
        if   self.power_type == "BIG":    self.left.height = 150; self.right.height = 150
        elif self.power_type == "SLOW":   self.speed[0] *= 0.6; self.speed[1] *= 0.6
        elif self.power_type == "FAST":   self.speed[0] *= 1.5; self.speed[1] *= 1.5
        elif self.power_type == "INVIS":  self.ball_visible = False
        elif self.power_type == "DOUBLE":
            self.extra_ball  = pygame.Rect(WIDTH // 2, HEIGHT // 2, 15, 15)
            self.extra_speed = [-self.speed[0], self.speed[1]]
        elif self.power_type == "REVERSE": self.reverse = True
        self.powerup = None

    def update_power(self):
        if self.power_active and time.time() - self.power_start > self.power_timer:
            self.left.height  = 100
            self.right.height = 100
            self.ball_visible = True
            self.reverse      = False
            self.extra_ball   = None
            sx = 5 if self.speed[0] > 0 else -5
            sy = 5 if self.speed[1] > 0 else -5
            self.speed        = [sx, sy]
            self.power_active = False

    # ── ball movement ────────────────────────────────────────────────────────
    def move_ball(self):
        self.ball.x += self.speed[0]
        self.ball.y += self.speed[1]

        if self.ball.top <= 0 or self.ball.bottom >= HEIGHT:
            self.speed[1] *= -1

        if self.ball.colliderect(self.left) or self.ball.colliderect(self.right):
            self.speed[0] *= -1

        if self.powerup and self.ball.colliderect(self.powerup):
            self.activate_power()

        if self.extra_ball:
            self.extra_ball.x += self.extra_speed[0]
            self.extra_ball.y += self.extra_speed[1]
            if self.extra_ball.top <= 0 or self.extra_ball.bottom >= HEIGHT:
                self.extra_speed[1] *= -1
            if self.extra_ball.colliderect(self.left) or self.extra_ball.colliderect(self.right):
                self.extra_speed[0] *= -1

        if self.ball.left <= 0:
            self.s2 += 1; self.reset_round()
        if self.ball.right >= WIDTH:
            self.s1 += 1; self.reset_round()

        if self.s1 >= WIN_SCORE:
            self.winner = self.name1 or "PLAYER 1"
            self.win_sound.play(); self.state = "WINNER"
        if self.s2 >= WIN_SCORE:
            self.winner = "COMPUTER" if self.mode == "COMPUTER" else (self.name2 or "PLAYER 2")
            self.win_sound.play(); self.state = "WINNER"

    def reset_round(self):
        self.ball.center = (WIDTH // 2, HEIGHT // 2)
        self.state       = "COUNTDOWN"
        self.count_start = time.time()

    # ── close button hit test ────────────────────────────────────────────────
    def _close_btn_rect_screen(self):
        """Return the close button rect in SCREEN coordinates."""
        if self.fullscreen:
            sw, sh = self.screen.get_size()
            sx = (WIDTH - 44) * sw // WIDTH
            sy = 8 * sh // HEIGHT
            sw2 = 36 * sw // WIDTH
            sh2 = 36 * sh // HEIGHT
            return pygame.Rect(sx, sy, sw2, sh2)
        return None

    # ── menu navigation helpers ──────────────────────────────────────────────
    def _clamp_menu(self, max_items):
        self.menu_sel = max(0, min(max_items - 1, self.menu_sel))

    # ── main loop ────────────────────────────────────────────────────────────
    def run(self):
        running = True
        while running:
            self.clock.tick(60)

            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False

                # ── mouse click (fullscreen close button) ──
                if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                    close = self._close_btn_rect_screen()
                    if close and close.collidepoint(e.pos):
                        self.fullscreen = False
                        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))

                if e.type == pygame.KEYDOWN:

                    # ── global shortcuts ──
                    if e.key == pygame.K_ESCAPE:
                        self.reset_all(); self.state = "WELCOME"; self.paused = False; continue

                    ctrl = pygame.key.get_mods() & pygame.KMOD_CTRL
                    if e.key == pygame.K_f and ctrl:
                        self.fullscreen = not self.fullscreen
                        self.screen = pygame.display.set_mode(
                            (0, 0) if self.fullscreen else (WIDTH, HEIGHT),
                            pygame.FULLSCREEN if self.fullscreen else 0
                        )
                    if e.key == pygame.K_m and ctrl:
                        self.reset_all(); self.state = "MAIN"; self.menu_sel = 0; continue

                    if e.key == pygame.K_h and ctrl:
                        self.state = "HELP"; continue

                    if e.key == pygame.K_p and self.state in ("PLAY", "COUNTDOWN"):
                        self.paused = not self.paused

                    if self.paused: continue

                    if e.key == pygame.K_h and self.state == "PLAY":
                        self._pre_help_state = self.state
                        self.state = "HELP_PAUSE"

                    # ── state-specific keys ──
                    if self.state == "WELCOME":
                        self.state = "MAIN"; self.menu_sel = 0

                    elif self.state == "MAIN":
                        if e.key == pygame.K_DOWN:  self.menu_sel = (self.menu_sel + 1) % 2
                        if e.key == pygame.K_UP:    self.menu_sel = (self.menu_sel - 1) % 2
                        if e.key in (pygame.K_1, pygame.K_KP1):
                            self.mode = "COMPUTER"; self.state = "LEVEL"; self.menu_sel = 0
                        elif e.key in (pygame.K_2, pygame.K_KP2):
                            self.mode = "MULTI"; self.state = "MODE_SELECT"; self.menu_sel = 0
                        elif e.key == pygame.K_RETURN:
                            if self.menu_sel == 0:
                                self.mode = "COMPUTER"; self.state = "LEVEL"; self.menu_sel = 0
                            else:
                                self.mode = "MULTI"; self.state = "MODE_SELECT"; self.menu_sel = 0

                    elif self.state == "LEVEL":
                        if e.key == pygame.K_DOWN: self.menu_sel = (self.menu_sel + 1) % 3
                        if e.key == pygame.K_UP:   self.menu_sel = (self.menu_sel - 1) % 3
                        levels = {0: [4,4], 1: [6,6], 2: [8,8]}
                        ai_cfg = {0: (4, 35, 0.08), 1: (6, 40, 0.05), 2: (8, 40, 0.03)}
                        chosen = None
                        if e.key in (pygame.K_1, pygame.K_KP1): chosen = 0
                        elif e.key in (pygame.K_2, pygame.K_KP2): chosen = 1
                        elif e.key in (pygame.K_3, pygame.K_KP3): chosen = 2
                        elif e.key == pygame.K_RETURN: chosen = self.menu_sel
                        if chosen is not None:
                            self.speed    = levels[chosen][:]
                            self.ai_speed, self.ai_error, self.ai_miss = ai_cfg[chosen]
                            self.input_prompt = "PLAYER 1 NAME"
                            self.state    = "NAME"

                    elif self.state == "MODE_SELECT":
                        if e.key == pygame.K_DOWN: self.menu_sel = (self.menu_sel + 1) % 2
                        if e.key == pygame.K_UP:   self.menu_sel = (self.menu_sel - 1) % 2
                        chosen = None
                        if e.key in (pygame.K_1, pygame.K_KP1): chosen = 0
                        elif e.key in (pygame.K_2, pygame.K_KP2): chosen = 1
                        elif e.key == pygame.K_RETURN: chosen = self.menu_sel
                        if chosen is not None:
                            self.submode = ["KEYBOARD", "PHONE"][chosen]
                            self.input_prompt = "PLAYER 1 NAME"
                            self.state = "NAME"

                    elif self.state == "NAME":
                        if e.key == pygame.K_RETURN:
                            nm = self.input_text.strip() or ("P1" if self.name1 == "" else "P2")
                            if self.mode == "COMPUTER":
                                self.name1 = nm; self.name2 = "AI"
                                self.state = "COUNTDOWN"; self.count_start = time.time()
                            else:
                                if self.name1 == "":
                                    self.name1 = nm
                                    self.input_prompt = "PLAYER 2 NAME"
                                else:
                                    self.name2 = nm
                                    self.state = "HELP"
                            self.input_text = ""
                        elif e.key == pygame.K_BACKSPACE:
                            self.input_text = self.input_text[:-1]
                        else:
                            if len(self.input_text) < 12:
                                self.input_text += e.unicode

                    elif self.state == "HELP":
                        self.state = "COUNTDOWN"; self.count_start = time.time()

                    elif self.state == "HELP_PAUSE":
                        self.state = "PLAY"

                    elif self.state == "WINNER":
                        if e.key == pygame.K_y:
                            self.reset_all()

            # ── drawing ──────────────────────────────────────────────────────
            if self.state == "WELCOME":
                self.draw_welcome()

            elif self.state == "MAIN":
                self.draw_main()

            elif self.state == "LEVEL":
                self.draw_level()

            elif self.state == "MODE_SELECT":
                self.draw_mode_select()

            elif self.state == "NAME":
                self.draw_name()

            elif self.state == "HELP":
                self.draw_help()

            elif self.state == "HELP_PAUSE":
                self.draw_game()
                self.draw_help()

            elif self.state == "COUNTDOWN":
                if self.paused:
                    self.draw_game()
                    self.draw_pause()
                else:
                    self.countdown()

            elif self.state == "PLAY":
                keys = pygame.key.get_pressed()
                if self.paused:
                    self.draw_game()
                    self.draw_pause()
                else:
                    if self.mode == "COMPUTER":
                        self.move_keyboard(keys)
                        self.move_ai()
                    else:
                        if self.submode == "KEYBOARD": self.move_keyboard(keys)
                        else: self.move_phone()

                    self.spawn_power()
                    self.update_power()

                    self.left.clamp_ip(self.base_surface.get_rect())
                    self.right.clamp_ip(self.base_surface.get_rect())

                    self.move_ball()
                    self.draw_game()

            elif self.state == "WINNER":
                self.draw_winner()

            # ── scale & flip ──────────────────────────────────────────────────
            if self.fullscreen:
                scaled = pygame.transform.scale(self.base_surface, self.screen.get_size())
                self.screen.blit(scaled, (0, 0))
            else:
                self.screen.blit(self.base_surface, (0, 0))

            pygame.display.flip()

        pygame.quit()
