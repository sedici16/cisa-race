"""Corsa Retro - a 1-bit top-down racing game for the fair kiosk.

Same look as "Game of Crowns" (game_templates/platformer): everything is drawn
with just two colours and pygame primitives - no image or sound files, one
self-contained script. Dodge the oncoming cars, grab coins, skim past traffic
for near-miss bonuses; the longer you drive the more you score and the faster
the road rushes at you.

Controls
    Left / Right ......... arrow keys or A / D
    Speed up ............. W or Up arrow (hold)
    Pause ............... Space
    Restart (after crash)  Space or R
    Quit ............... Esc or Q
"""
import math
import os
import random
from sys import exit as sys_exit

import pygame

import kiosk_joy
import kiosk_screen

pygame.init()
kiosk_joy.init()

# ------------------------------------------------------------------ look & feel
# retro 1-bit dungeon palette - identical to Game of Crowns
DARK = (13, 13, 18)
LITE = (200, 192, 170)
PROGRESS_DOT = (206, 46, 46)   # puntino rosso che segna l'auto sulla mappa laterale
YELLOW = (255, 255, 0)
GREY = (200, 200, 200)
BLUE = (60, 110, 220)
WHITE = (255, 255, 255)
VOLVO_W, VOLVO_H = 40, 80

ARMORED_CHANCE = 0.2   # quota di auto nemiche blindate
ARMORED_HP = 3         # colpi di mitra necessari per distruggerle

WIN_W, WIN_H = 800, 660
FPS = 60

# ------------------------------------------------------------- gameplay knobs
# (all easy to tweak by prompt: "rendi l'auto piu veloce", "aggiungi piu
#  traffico", "allarga la strada", "piu monete", "bonus sorpasso piu alto"...)
ROAD_W = 460                # width of the drivable road, centred on screen
PLAYER_STEER_SPEED = 9      # how fast you slide left / right
START_SPEED = 7.5           # how fast the world rushes toward you at the start
SPEED_PER_LEVEL = 0.675     # extra world speed gained each level
BOOST_EXTRA = 7.5           # extra speed while holding W / Up
LEVEL_EVERY = 1200          # points between levels
ENEMY_COUNT = 3             # oncoming cars on the road at once

COIN_COUNT = 3             # coins on the road at once
COIN_BONUS = 25            # points per coin
PUDDLE_COUNT = 2          # oil / water patches at once
SLIP_FRAMES = 55         # how long you lose grip after hitting a patch
NEARMISS_GAP = 20        # extra px clearance that still counts as a near miss
NEARMISS_BONUS = 50     # points for skimming past an enemy without crashing
CRASH_FRAMES = 34      # length of the crash animation before GAME OVER
HIT_INVULN_FRAMES = FPS      # invulnerabilita' dopo un colpo non fatale (perdi una vita)

SMOKE_SPAWN_EVERY = 3    # frame tra un puff di fumo e il successivo mentre acceleri
SMOKE_LIFE = 30          # durata di ogni puff (frame) prima di sparire
SMOKE_R0, SMOKE_R1 = 3, 11   # raggio iniziale/finale (si allarga e si dirada)

SHIELD_R = 13               # raggio dell'icona scudo
SHIELD_COUNT = 1            # scudi presenti sulla strada contemporaneamente
SHIELD_FRAMES = FPS * 3     # durata dell'invincibilita' dopo aver preso lo scudo
PITSTOP_EXIT_SHIELD_FRAMES = FPS * 2   # scudo gratis quando si rientra in strada dal pit stop

MITRA_R = 11                # raggio della mitra doppia
MITRA_COUNT = 1             # mitras presenti sulla strada contemporaneamente
MITRA_FRAMES = FPS * 3      # durata del boost della mitra doppia (3 secondi)
MITRA_SPEED_BOOST = 1.5     # moltiplicatore di velocita'

BULLET_W, BULLET_H = 5, 16      # proiettili del doppio sparo
BULLET_SPEED = 16               # quanto i proiettili sono piu' veloci dell'auto (relativo a eff)
BULLET_FIRE_INTERVAL = 10       # frame tra una raffica e la successiva (mentre mitra e' attiva)
BULLET_SIDE_OFFSET = 10         # quanto sono distanziati i due colpi dal centro dell'auto
BULLET_SCORE = 15               # punti per ogni auto nemica colpita

# power-up acquistabili al pit stop
SUPER_SHIELD_PRICE = 10
SUPER_SHIELD_FRAMES = FPS * 10   # dura di piu' dello scudo normale e protegge anche dalle blindate

TRIPLE_SHOT_PRICE = 15
TRIPLE_SHOT_FRAMES = FPS * 7
TRIPLE_SPEED = 14                # velocita' dei colpi laterali (orizzontale)
PASTICCERIA_HP = 1                # colpi di sparo triplo per distruggere una pasticceria

EXTRA_LIFE_PRICE = 12

PIT_ITEMS = [
    {"key": "super_shield", "name": "Super Scudo", "price": SUPER_SHIELD_PRICE,
     "desc": "10s, protegge anche dalle blindate"},
    {"key": "triple_shot", "name": "Sparo Triplo", "price": TRIPLE_SHOT_PRICE,
     "desc": "7s, davanti + laterale, distrugge le pasticcerie"},
    {"key": "extra_life", "name": "Vita Extra", "price": EXTRA_LIFE_PRICE,
     "desc": "+1 vita"},
]

# prezzi del pit stop personalizzati per auto (indice = selected_car:
# 0 Maggiolino, 1 BMW, 2 Volvo); una voce assente usa il prezzo base sopra
SUPER_SHIELD_PRICE_BY_CAR = {0: 20, 1: 25, 2: 30}
EXTRA_LIFE_PRICE_BY_CAR = {0: 20, 1: 25, 2: 30}

UFO_W, UFO_H = 70, 28          # mothership aliena stile Space Invaders
UFO_SPEED = 4.8                # vola sempre da sinistra a destra
UFO_Y = 46                     # altezza fissa vicino al bordo superiore
UFO_WAIT_MIN = 360             # frame minimi prima della prossima apparizione
UFO_WAIT_MAX = 700             # frame massimi prima della prossima apparizione
MUSHROOM_W, MUSHROOM_H = 18, 16       # i "funghetti" lanciati dalla mothership
MUSHROOM_DROP_EVERY = 45              # ogni quanti frame lancia un oggetto mentre e' in volo
MUSHROOM_BOOST_FRAMES = FPS * 5       # il funghetto spinge l'auto per 5 secondi
SPIKE_W, SPIKE_H = 20, 14             # gli "spikes" lanciati dalla mothership

# ondata aliena ("ORDA"): scatta tra una citta' e l'altra, 15s di astronavi
# a raffica che bombardano solo spikes; niente auto nemiche/cantieri/pitstop
HORDE_DURATION = FPS * 7
HORDE_UFO_COUNT = 3          # astronavi contemporanee sullo schermo durante l'ondata
HORDE_UFO_WAIT_MIN = 35      # attesa minima tra un'astronave e la successiva durante l'ondata
HORDE_UFO_WAIT_MAX = 70
HORDE_UFO_SPEED = UFO_SPEED * 2.2
HORDE_DROP_EVERY = 22        # lasciano cadere spikes piu' spesso del normale MUSHROOM_DROP_EVERY
HORDE_SPEED_MULT = 1.15      # +15% velocita' effettiva durante l'ondata

MOTO_W, MOTO_H = 22, 50        # moto pazza che sfreccia contromano ogni tanto
MOTO_EXTRA_SPEED = 4.0         # quanto e' piu' veloce delle auto normali
MOTO_WAIT_MIN = 500            # frame minimi prima della prossima moto
MOTO_WAIT_MAX = 950            # frame massimi prima della prossima moto

DONKEY_W, DONKEY_H = 64, 72    # asino grigio (grosso) che attraversa la strada perpendicolarmente
DONKEY_SPEED = 2.0             # velocita' orizzontale, molto lenta (da sinistra a destra)
DONKEY_FALL_SPEED = 3.5        # scende (non legata a eff, molto piu' lenta del traffico normale)
                                # finche' non raggiunge DONKEY_ROW_Y, poi resta li' e continua solo
                                # in orizzontale - da' qualche secondo per vederlo arrivare da in
                                # alto prima che diventi un vero pericolo sulla riga dell'auto
DONKEY_ROW_Y = 550              # altezza a cui si "ferma" (in linea con l'auto)
DONKEY_WAIT_MIN = 400          # frame minimi prima della prossima apparizione
DONKEY_WAIT_MAX = 800          # frame massimi prima della prossima apparizione

PASTICCERIA_W, PASTICCERIA_H = 92, 118   # negozietto decorativo sul bordo strada
PASTICCERIA_WAIT_MIN = 500      # frame minimi prima della prossima apparizione
PASTICCERIA_WAIT_MAX = 1100     # frame massimi prima della prossima apparizione

# Pit stop: piazzola che allarga la corsia (a sinistra), ci entri guidando e
# si apre un negozio di power-up. Ricompare a intervalli casuali per tutta la
# corsa, ogni volta tra 10 e 30 secondi dopo la precedente.
PITSTOP_WAIT_MIN = FPS * 10       # attesa minima prima del prossimo pit stop
PITSTOP_WAIT_MAX = FPS * 30       # attesa massima prima del prossimo pit stop
PITSTOP_DURATION = FPS * 6        # per quanto resta aperta la piazzola se non ci entri
PITSTOP_LANE_EXTRA = 110          # larghezza della piazzola oltre il bordo destro della strada
PITSTOP_ENTER_FRAMES = FPS * 1.2  # durata della "frenata e parcheggio" prima che si apra il menu

TOWNS = ["Borgotaro", "Berceto", "Pontremoli", "Filattiera", "Villafranca", "Aulla",
         "S. Stefano Magra", "Sarzana", "Luni", "Carrara", "Massa"]      # cartelli di citta' raggiunta, uno ogni TOWN_EVERY punti
CONSTRUCTION_SEGMENTS = [1, 2]  # segmenti dove i lavori appaiono: tra Borgotaro-Berceto (1) e Berceto-Pontremoli (2)
TOWN_EVERY = 2000                 # punti tra un cartello e il successivo
TOWN_BANNER_FRAMES = 150          # quanto resta a schermo il cartello

CONSTRUCTION_MIN_WAIT = 800       # frame prima del prossimo cantiere
CONSTRUCTION_MAX_WAIT = 1500      # frame massimi prima della prossima apparizione
CONSTRUCTION_DURATION = 300       # frame di durata della modalita' cantiere
CONSTRUCTION_ROAD_W = 230         # larghezza strada durante cantiere (circa meta')

CAR_W, CAR_H = 40, 64
COIN_R = 8
PUD_W, PUD_H = 72, 28

HS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "high_scores.txt")
LIFETIME_COINS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lifetime_coins.txt")
GOLF_ANNOUNCED_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "golf_announced.txt")
GOLF_UNLOCK_COINS = 200   # monete totali (tra tutte le partite) per sbloccare la Golf Cabrio


def make_player_car():
    """Your car: a solid yellow body, dark glass near the top (it faces up)."""
    s = pygame.Surface((CAR_W, CAR_H), pygame.SRCALPHA)
    pygame.draw.rect(s, YELLOW, (3, 2, CAR_W - 6, CAR_H - 4))          # body
    pygame.draw.rect(s, DARK, (8, 7, CAR_W - 16, 12))              # windshield
    pygame.draw.rect(s, DARK, (10, 41, CAR_W - 20, 9))            # rear window
    for wy in (13, CAR_H - 25):                                    # dark wheels
        pygame.draw.rect(s, DARK, (0, wy, 4, 13))
        pygame.draw.rect(s, DARK, (CAR_W - 4, wy, 4, 13))
    return s


def make_player_car_bmw():
    """BMW Z3: sportier, sleeker profile with aggressive windshield."""
    s = pygame.Surface((CAR_W, CAR_H), pygame.SRCALPHA)
    pygame.draw.rect(s, LITE, (2, 6, CAR_W - 4, CAR_H - 14))        # body (sleeker)
    pygame.draw.rect(s, DARK, (6, 9, CAR_W - 12, 11))              # windshield (higher)
    pygame.draw.rect(s, DARK, (8, 40, CAR_W - 16, 10))             # rear window
    pygame.draw.polygon(s, DARK, [(3, 6), (CAR_W - 3, 6), (CAR_W - 2, 2), (2, 2)])  # front slope
    for wy in (16, CAR_H - 23):                                     # wheels
        pygame.draw.rect(s, DARK, (0, wy, 5, 12))
        pygame.draw.rect(s, DARK, (CAR_W - 5, wy, 5, 12))
    return s


def make_player_car_volvo():
    """Volvo: longer car with light body and prominent front grille."""
    s = pygame.Surface((VOLVO_W, VOLVO_H), pygame.SRCALPHA)
    pygame.draw.rect(s, LITE, (3, 4, VOLVO_W - 6, VOLVO_H - 8))     # body (longer)
    pygame.draw.rect(s, DARK, (7, 8, VOLVO_W - 14, 12))            # windshield
    pygame.draw.rect(s, DARK, (7, 50, VOLVO_W - 14, 10))           # rear window
    for wy in (18, VOLVO_H - 23):                                   # wheels
        pygame.draw.rect(s, DARK, (0, wy, 5, 12))
        pygame.draw.rect(s, DARK, (VOLVO_W - 5, wy, 5, 12))
    return s


def make_player_car_golf():
    """Golf Cabrio: cabrio sbloccabile, capote abbassata - niente vetri
    scuri separati come le altre auto, solo l'abitacolo a vista e la
    capote ripiegata dietro."""
    s = pygame.Surface((CAR_W, CAR_H), pygame.SRCALPHA)
    pygame.draw.rect(s, PROGRESS_DOT, (3, 2, CAR_W - 6, CAR_H - 4))     # body (rosso)
    pygame.draw.rect(s, DARK, (8, 10, CAR_W - 16, CAR_H - 34))         # abitacolo a vista
    pygame.draw.rect(s, DARK, (6, CAR_H - 22, CAR_W - 12, 8))          # capote ripiegata
    for wy in (13, CAR_H - 25):
        pygame.draw.rect(s, DARK, (0, wy, 4, 13))
        pygame.draw.rect(s, DARK, (CAR_W - 4, wy, 4, 13))
    return s


def make_enemy_car():
    """Oncoming car: grey body with glass near the BOTTOM and a bold
    dark chevron pointing down so you read it as coming straight at you."""
    s = pygame.Surface((CAR_W, CAR_H), pygame.SRCALPHA)
    pygame.draw.rect(s, GREY, (3, 2, CAR_W - 6, CAR_H - 4))          # body
    pygame.draw.rect(s, DARK, (8, CAR_H - 19, CAR_W - 16, 12))     # windshield
    pygame.draw.polygon(s, DARK, [                                 # downward chevron
        (6, 12), (CAR_W // 2, 26), (CAR_W - 6, 12),
        (CAR_W - 6, 20), (CAR_W // 2, 34), (6, 20),
    ])
    for wy in (13, CAR_H - 25):
        pygame.draw.rect(s, DARK, (0, wy, 4, 13))
        pygame.draw.rect(s, DARK, (CAR_W - 4, wy, 4, 13))
    return s


def make_enemy_car_armored():
    """Auto blindata: corpo blu con placche di corazza scure - serve piu'
    di un colpo di mitra per distruggerla e lo scudo non protegge da lei."""
    s = pygame.Surface((CAR_W, CAR_H), pygame.SRCALPHA)
    pygame.draw.rect(s, BLUE, (3, 2, CAR_W - 6, CAR_H - 4))          # body
    pygame.draw.rect(s, DARK, (8, CAR_H - 19, CAR_W - 16, 12))     # windshield
    pygame.draw.polygon(s, DARK, [                                 # downward chevron
        (6, 12), (CAR_W // 2, 26), (CAR_W - 6, 12),
        (CAR_W - 6, 20), (CAR_W // 2, 34), (6, 20),
    ])
    for py0 in (2, CAR_H // 2 - 3, CAR_H - 18):                    # placche di corazza
        pygame.draw.rect(s, DARK, (5, py0, CAR_W - 10, 4))
    for wy in (13, CAR_H - 25):
        pygame.draw.rect(s, DARK, (0, wy, 4, 13))
        pygame.draw.rect(s, DARK, (CAR_W - 4, wy, 4, 13))
    return s


def make_coin():
    s = pygame.Surface((COIN_R * 2 + 2, COIN_R * 2 + 2), pygame.SRCALPHA)
    c = COIN_R + 1
    pygame.draw.circle(s, LITE, (c, c), COIN_R, 2)
    pygame.draw.circle(s, LITE, (c, c), 2)
    return s


def make_shield():
    """Icona scudo: sagoma chiara con bordo scuro e una croce al centro."""
    d = SHIELD_R * 2 + 2
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = SHIELD_R + 1
    pts = [(c, 1), (d - 2, c - 2), (d - 2, c + 4),
           (c, d - 1), (2, c + 4), (2, c - 2)]
    pygame.draw.polygon(s, LITE, pts)
    pygame.draw.polygon(s, DARK, pts, 2)
    pygame.draw.rect(s, DARK, (c - 2, c - 6, 4, 8))
    pygame.draw.rect(s, DARK, (c - 6, c - 2, 12, 4))
    return s


def make_mitra():
    """Icona mitra doppia: rossa per distinguerla dagli altri power-up chiari,
    copricapo con bordo, due punte per significare 'doppia'."""
    d = MITRA_R * 2 + 2
    s = pygame.Surface((d, d), pygame.SRCALPHA)
    c = MITRA_R + 1
    pygame.draw.rect(s, PROGRESS_DOT, (c - 8, c - 2, 16, 8))
    pygame.draw.polygon(s, PROGRESS_DOT, [(c - 6, c - 2), (c - 2, 1), (c + 2, 1), (c + 6, c - 2)])
    pygame.draw.polygon(s, DARK, [(c - 6, c - 2), (c - 2, 1), (c + 2, 1), (c + 6, c - 2)], 2)
    pygame.draw.rect(s, DARK, (c - 8, c - 2, 16, 8), 2)
    pygame.draw.rect(s, DARK, (c - 4, c + 6, 8, 2))
    return s


def make_puddle():
    """A dark oil slick - invisible fill on the dark road, read from its dotted
    light rim and a couple of inner shimmer specks."""
    s = pygame.Surface((PUD_W, PUD_H), pygame.SRCALPHA)
    pygame.draw.ellipse(s, DARK, (0, 0, PUD_W, PUD_H))
    for a in range(0, 360, 14):
        r = math.radians(a)
        x = PUD_W / 2 + (PUD_W / 2 - 2) * math.cos(r)
        y = PUD_H / 2 + (PUD_H / 2 - 2) * math.sin(r)
        if 0 <= x < PUD_W and 0 <= y < PUD_H:
            s.set_at((int(x), int(y)), LITE)
    for sx, sy in ((PUD_W * 0.35, PUD_H * 0.45), (PUD_W * 0.6, PUD_H * 0.6)):
        s.set_at((int(sx), int(sy)), LITE)
    return s


def make_ufo():
    """Mothership aliena stile Space Invaders: scafo scuro, cupola chiara."""
    s = pygame.Surface((UFO_W, UFO_H), pygame.SRCALPHA)
    pygame.draw.ellipse(s, LITE, (0, UFO_H // 2 - 4, UFO_W, UFO_H // 2 + 4))
    pygame.draw.ellipse(s, DARK, (UFO_W // 2 - 14, 0, 28, UFO_H // 2 + 6))
    for wx in range(10, UFO_W - 10, 12):
        pygame.draw.rect(s, DARK, (wx, UFO_H // 2 + 2, 4, 4))
    return s


def make_mushroom():
    """Piccolo fungo lanciato dalla mothership: cappello chiaro, gambo scuro."""
    s = pygame.Surface((MUSHROOM_W, MUSHROOM_H), pygame.SRCALPHA)
    pygame.draw.ellipse(s, LITE, (0, 0, MUSHROOM_W, MUSHROOM_H * 2 // 3))
    pygame.draw.rect(s, DARK, (MUSHROOM_W // 2 - 3, MUSHROOM_H * 2 // 3 - 2,
                                6, MUSHROOM_H // 3 + 2))
    for sx, sy in ((3, 3), (MUSHROOM_W - 5, 4)):
        s.set_at((sx, sy), DARK)
    return s


def make_spike():
    """Trappola a punte lanciata dalla mothership: fa esplodere l'auto."""
    s = pygame.Surface((SPIKE_W, SPIKE_H), pygame.SRCALPHA)
    pygame.draw.rect(s, DARK, (0, SPIKE_H - 4, SPIKE_W, 4))
    for x0 in range(0, SPIKE_W, 5):
        pygame.draw.polygon(s, YELLOW, [
            (x0, SPIKE_H - 4), (x0 + 2, 0), (x0 + 4, SPIKE_H - 4),
        ])
    return s


def make_moto():
    """Moto contromano: ruote e manubrio chiari per essere ben visibili sulla
    strada scura, telaio chiaro con motore scuro al centro."""
    s = pygame.Surface((MOTO_W, MOTO_H), pygame.SRCALPHA)
    cx = MOTO_W // 2
    pygame.draw.circle(s, LITE, (cx, 9), 7)                            # ruota davanti
    pygame.draw.circle(s, DARK, (cx, 9), 3)                             # mozzo
    pygame.draw.circle(s, LITE, (cx, MOTO_H - 9), 7)                   # ruota dietro
    pygame.draw.circle(s, DARK, (cx, MOTO_H - 9), 3)                    # mozzo
    pygame.draw.rect(s, LITE, (cx - 4, 9, 8, MOTO_H - 18))              # telaio/sella
    pygame.draw.rect(s, DARK, (cx - 4, MOTO_H // 2 - 4, 8, 8))         # motore
    pygame.draw.rect(s, LITE, (cx - 7, 5, 14, 4))                       # manubrio
    return s


def make_donkey():
    """Asino grigio che attraversa la strada da sinistra a destra:
    corpo grigio grosso con testa, orecchie lunghe, zampe e coda scure."""
    s = pygame.Surface((DONKEY_W, DONKEY_H), pygame.SRCALPHA)
    pygame.draw.ellipse(s, GREY, (10, 30, 44, 30))                # corpo
    pygame.draw.circle(s, GREY, (48, 24), 9)                       # testa (a destra)
    pygame.draw.polygon(s, GREY, [(54, 18), (56, 2), (49, 17)])    # orecchio sinistro (lungo)
    pygame.draw.polygon(s, GREY, [(46, 17), (42, 1), (40, 18)])    # orecchio destro (lungo)
    pygame.draw.circle(s, DARK, (46, 22), 2)                       # occhio
    for zx in (13, 21, 35, 43):                                    # zampe
        pygame.draw.rect(s, GREY, (zx, 56, 5, 14))
    pygame.draw.line(s, DARK, (10, 42), (3, 34), 3)               # coda
    return s


def make_pasticceria():
    """Pasticceria decorativa sul bordo strada: edificio con tettoia a righe
    rosse e insegna col nome - puro sfondo, nessuna collisione col giocatore."""
    w, h = PASTICCERIA_W, PASTICCERIA_H
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    body_top = 46
    pygame.draw.rect(s, LITE, (6, body_top, w - 12, h - body_top - 4))     # corpo edificio
    pygame.draw.rect(s, DARK, (6, body_top, w - 12, h - body_top - 4), 2)
    pygame.draw.polygon(s, DARK, [(2, body_top), (w // 2, 4), (w - 2, body_top)])  # tetto

    awning_y = body_top + 4                          # tendina a righe sopra la vetrina
    stripe_w = (w - 20) // 6
    for i in range(6):
        color = PROGRESS_DOT if i % 2 == 0 else LITE
        pygame.draw.rect(s, color, (10 + i * stripe_w, awning_y, stripe_w, 10))
    pygame.draw.polygon(s, DARK, [(10, awning_y + 10), (16, awning_y + 18), (10, awning_y + 18)])
    pygame.draw.polygon(s, DARK, [(w - 10, awning_y + 10), (w - 16, awning_y + 18), (w - 10, awning_y + 18)])

    pygame.draw.rect(s, DARK, (w // 2 - 10, h - 34, 20, 30))               # porta

    font = pygame.font.Font(None, 15)
    label = font.render("PASTICCERIA", True, DARK)
    lbl_bg = pygame.Rect(0, 0, label.get_width() + 6, label.get_height() + 2)
    lbl_bg.center = (w // 2, body_top - 8)
    pygame.draw.rect(s, LITE, lbl_bg)
    pygame.draw.rect(s, DARK, lbl_bg, 1)
    s.blit(label, label.get_rect(center=lbl_bg.center))
    return s


def make_background():
    """Dithered dungeon-brick wall, tiled so it wraps seamlessly when scrolled
    vertically. Same trick as Game of Crowns."""
    bg = pygame.Surface((WIN_W, WIN_H))
    bg.fill(DARK)
    bw, bh = 60, 30                       # WIN_H is an exact multiple of bh -> no seam
    for row, yy in enumerate(range(0, WIN_H, bh)):
        off = 0 if row % 2 == 0 else bw // 2
        for x0 in range(-bw, WIN_W + bw, bw):
            x = x0 + off
            for dx in range(0, bw, 4):
                if 0 <= x + dx < WIN_W:
                    bg.set_at((x + dx, yy), LITE)
            for dy in range(0, bh, 4):
                if 0 <= x < WIN_W and yy + dy < WIN_H:
                    bg.set_at((x, yy + dy), LITE)
    return bg


def _render_pixel_text(font, text, color, block=6):
    """Render text then shrink it and blow it back up (nearest-neighbour, no
    smoothing) for a chunky retro-pixel look, used for the "Cisa Race" logo."""
    raw = font.render(text, False, color)
    w, h = raw.get_size()
    small = pygame.transform.scale(raw, (max(1, w // block), max(1, h // block)))
    return pygame.transform.scale(small, (w, h))


def _star_points(cx, cy, r):
    pts = []
    for i in range(10):
        rad = r if i % 2 == 0 else r * 0.42
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + rad * math.cos(a), cy + rad * math.sin(a)))
    return pts


class Race:
    def __init__(self):
        self.screen = kiosk_screen.setup(WIN_W, WIN_H, "Corsa Retro")
        self.canvas = pygame.Surface((WIN_W, WIN_H))
        self.clock = pygame.time.Clock()

        self.bg = make_background()
        self.player_img_beetle = make_player_car()
        self.player_car_bmw = make_player_car_bmw()
        self.player_car_volvo = make_player_car_volvo()
        self.player_car_golf = make_player_car_golf()
        self.player_img = self.player_img_beetle
        self.enemy_img = make_enemy_car()
        self.enemy_img_armored = make_enemy_car_armored()
        self.coin_img = make_coin()
        self.shield_img = make_shield()
        self.mitra_img = make_mitra()
        self.puddle_img = make_puddle()
        self.moto_img = make_moto()
        self.donkey_img = make_donkey()
        self.pasticceria_img = make_pasticceria()
        self.ufo_img = make_ufo()
        self.mushroom_img = make_mushroom()
        self.spike_img = make_spike()
        self.hud_font = pygame.font.Font(None, 32)
        self.logo_font = pygame.font.Font(None, 145)
        self.big_font = pygame.font.Font(None, 90)
        self.mid_font = pygame.font.Font(None, 34)
        self.pop_font = pygame.font.Font(None, 30)
        self.progress_font = pygame.font.Font(None, 18)

        self.road_left = (WIN_W - ROAD_W) // 2
        self.road_right = self.road_left + ROAD_W

        self.max_score = self._load_hs()
        self.lifetime_coins = self._load_lifetime_coins()
        self.golf_unlocked = self.lifetime_coins >= GOLF_UNLOCK_COINS
        self.golf_announced = self._load_golf_announced()
        # se sbloccata ma non ancora "vista" nel menu (anche in una sessione
        # precedente, se il gioco e' stato chiuso/riavviato nel frattempo)
        self.golf_newly_unlocked = self.golf_unlocked and not self.golf_announced
        self.selected_car = 0
        self.reset()
        self.state = "SELECT_CAR"

    # ------------------------------------------------------------- high score
    def _load_hs(self):
        try:
            with open(HS_PATH) as f:
                vals = [int(float(x)) for x in f.read().split()]
            return max(vals) if vals else 0
        except (OSError, ValueError):
            return 0

    def _save_hs(self):
        try:
            with open(HS_PATH, "w") as f:
                f.write(str(self.max_score))
        except OSError:
            pass

    def _car_unlocked(self, idx):
        return idx != 3 or self.golf_unlocked

    def _dismiss_golf_banner(self):
        if self.golf_newly_unlocked:
            self.golf_newly_unlocked = False
            self.golf_announced = True
            self._save_golf_announced()

    def _load_lifetime_coins(self):
        try:
            with open(LIFETIME_COINS_PATH) as f:
                return max(0, int(float(f.read().strip())))
        except (OSError, ValueError):
            return 0

    def _save_lifetime_coins(self):
        try:
            with open(LIFETIME_COINS_PATH, "w") as f:
                f.write(str(self.lifetime_coins))
        except OSError:
            pass

    def _load_golf_announced(self):
        return os.path.exists(GOLF_ANNOUNCED_PATH)

    def _save_golf_announced(self):
        try:
            with open(GOLF_ANNOUNCED_PATH, "w") as f:
                f.write("1")
        except OSError:
            pass

    # ------------------------------------------------------------- round setup
    def _lane_bounds(self, w=CAR_W):
        left = self.road_left + 6
        right = self.road_right - 6 - w
        if self.construction_mode:
            if self.construction_side == "left":
                right = left + CONSTRUCTION_ROAD_W - 12 - w
            else:
                left = right - (CONSTRUCTION_ROAD_W - 12 - w)
        elif self.pitstop_active:
            left -= PITSTOP_LANE_EXTRA
        return left, right

    def reset(self):
        extra_lives = 0
        self.car_coin_mult = 1.0
        if self.selected_car == 0:
            self.player_img = self.player_img_beetle
            self.player_car_w, self.player_car_h = CAR_W, CAR_H
            self.car_speed_mult = 1.10   # Maggiolino: 10% piu veloce
            self.car_slip_mult = 1.0
        elif self.selected_car == 1:
            self.player_img = self.player_car_bmw
            self.player_car_w, self.player_car_h = CAR_W, CAR_H
            self.car_speed_mult = 1.0
            self.car_slip_mult = 0.5     # BMW: slitta meno nelle pozzanghere
        elif self.selected_car == 2:
            self.player_img = self.player_car_volvo
            self.player_car_w, self.player_car_h = VOLVO_W, VOLVO_H
            self.car_speed_mult = 0.95   # Volvo: 5% piu lenta
            self.car_slip_mult = 1.0
            extra_lives = 1               # ...ma una vita in piu
        else:
            self.player_img = self.player_car_golf
            self.player_car_w, self.player_car_h = CAR_W, CAR_H
            self.car_speed_mult = 1.0
            self.car_slip_mult = 1.0
            self.car_coin_mult = 1.2     # Golf Cabrio (sbloccabile): +20% monete
        self.score = 0
        self.coins_got = 0
        self.level = 0
        self.speed = START_SPEED * self.car_speed_mult
        self.scroll = 0.0
        self.slip = 0
        self.shake = 0.0
        self.crash_timer = 0
        self.crash_pos = (0, 0)
        self.lives = 3 + extra_lives
        self.hit_invuln = 0          # frame di invulnerabilita' dopo l'ultimo colpo
        self.state = "PLAY"                       # PLAY / PAUSE / CRASH / OVER / WIN
        self.px = (self.road_left + self.road_right) / 2 - self.player_car_w / 2
        self.py = WIN_H - self.player_car_h - 24
        self.town_idx = 0
        self.town_banner = None
        self.horde_active = False
        self.horde_timer = 0
        self.horde_ufos = []        # {x, y, speed, drop_in} astronavi dello sciame durante l'ondata
        self.horde_ufo_wait = 0
        self.construction_mode = False
        self.construction_side = "left"      # ridefinito a caso ogni volta che il cantiere appare
        self.construction_timer = 0
        self.construction_wait = random.randint(CONSTRUCTION_MIN_WAIT, CONSTRUCTION_MAX_WAIT)
        self.construction_segment_done = set()  # traccia quali segmenti hanno gia' avuto i lavori

        self.pitstop_wait = random.randint(PITSTOP_WAIT_MIN, PITSTOP_WAIT_MAX)  # deve
        self.pitstop_active = False     # esistere prima della prima _lane_bounds() qui sotto
        self.pitstop_timer = 0
        self.pitstop_entering = False   # fase di frenata/parcheggio prima del menu
        self.pitstop_enter_timer = 0
        self.pitstop_target_x = 0.0
        self.pitstop_cursor = 0
        self.pitstop_nav_cooldown = 0
        self.pitstop_msg = ""            # messaggio temporaneo nel menu (es. "monete insufficienti")

        self.super_shield_timer = 0
        self.triple_timer = 0
        self.triple_fire_cooldown = 0

        lo, hi = self._lane_bounds()
        self.enemies = [
            self._new_enemy(random.uniform(lo, hi), -200.0 - i * 260)
            for i in range(ENEMY_COUNT)
        ]
        clo, chi = self._lane_bounds(COIN_R * 2)
        self.coins = [{"x": random.uniform(clo, chi), "y": -140.0 - i * 230}
                      for i in range(COIN_COUNT)]
        plo, phi = self._lane_bounds(PUD_W)
        self.puddles = [{"x": random.uniform(plo, phi), "y": -500.0 - i * 360}
                        for i in range(PUDDLE_COUNT)]
        slo, shi = self._lane_bounds(SHIELD_R * 2)
        self.shields = [{"x": random.uniform(slo, shi), "y": -900.0 - i * 700}
                        for i in range(SHIELD_COUNT)]
        self.shield_timer = 0       # frame di invincibilita' rimasti

        mlo, mhi = self._lane_bounds(MITRA_R * 2)
        self.mitras = [{"x": random.uniform(mlo, mhi), "y": -1200.0 - i * 800}
                       for i in range(MITRA_COUNT)]
        self.mitra_timer = 0        # frame di boost/sparo della mitra rimasti
        self.mitra_fire_cooldown = 0
        self.bullets = []           # {x, y} proiettili del doppio sparo

        self.moto = None
        self.moto_wait = random.randint(MOTO_WAIT_MIN, MOTO_WAIT_MAX)

        self.donkey = None
        self.donkey_wait = FPS * 2     # il primo asino arriva subito, dopo 2 secondi dall'inizio

        self.pasticceria = None        # {x, y, side} decorazione sul bordo strada
        self.pasticceria_wait = random.randint(PASTICCERIA_WAIT_MIN, PASTICCERIA_WAIT_MAX)

        self.ufo = None
        self.ufo_wait = random.randint(UFO_WAIT_MIN, UFO_WAIT_MAX)
        self.mushrooms = []         # {x, y, kind} funghetti / spikes lanciati dalla mothership
        self.boost_timer = 0        # frame di spinta extra rimasti dopo un funghetto

        self.popups = []            # {x, y, txt, life}
        self.confetti = []          # {x, y, vx, vy}
        self.smoke = []              # {x, y, vx, vy, age, life} puff dallo scarico
        self.smoke_cooldown = 0
        self.record_timer = 0
        self.amor_timer = 0
        self.unlock_timer = 0
        self.start_max = self.max_score
        self.beaten_record = False
        self.anim_frame = 0

    def _filter_construction_zone(self):
        """Sposta (non elimina) nemici, monete, scudi, mitre e pozze che si
        trovano nella corsia chiusa per lavori dentro la corsia libera - a
        sinistra o a destra a seconda di self.construction_side. Prima questi
        oggetti venivano tolti dalle liste e mai rimpiazzati: con due cantieri
        lungo il percorso si finiva per perdere auto nemiche per sempre."""
        if self.construction_side == "left":
            def out_of_lane(x, w):
                return x + w > self.road_left + CONSTRUCTION_ROAD_W
        else:
            def out_of_lane(x, w):
                return x < self.road_right - CONSTRUCTION_ROAD_W

        def reposition(items, w):
            lo, hi = self._lane_bounds(w)
            for it in items:
                if out_of_lane(it["x"], w):
                    it["x"] = random.uniform(lo, hi)

        reposition(self.enemies, CAR_W)
        reposition(self.coins, COIN_R * 2)
        reposition(self.shields, SHIELD_R * 2)
        reposition(self.mitras, MITRA_R * 2)
        reposition(self.puddles, PUD_W)

    def _new_enemy(self, x, y):
        armored = random.random() < ARMORED_CHANCE
        return {
            "x": x, "y": y, "scored": False,
            "armored": armored, "hp": ARMORED_HP if armored else 1,
        }

    def _respawn_enemy(self, e):
        lo, hi = self._lane_bounds()
        e["y"] = random.uniform(-320, -80)
        e["scored"] = False
        e["armored"] = random.random() < ARMORED_CHANCE
        e["hp"] = ARMORED_HP if e["armored"] else 1
        x = random.uniform(lo, hi)
        for _ in range(12):
            if all(o is e or o["y"] > 60 or abs(x - o["x"]) > CAR_W + 12
                   for o in self.enemies):
                break
            x = random.uniform(lo, hi)
        e["x"] = x

    def _recycle(self, obj, w, y_lo, y_hi):
        lo, hi = self._lane_bounds(w)
        obj["x"] = random.uniform(lo, hi)
        obj["y"] = random.uniform(y_lo, y_hi)

    # ------------------------------------------------------------- main loop
    def run(self):
        while True:
            self.handle_events()
            if kiosk_joy.wants_quit():
                self.quit()
            if self.state == "PLAY":
                self.update()
            elif self.state == "CRASH":
                self.crash_step()
            if self.state not in ("PAUSE", "SELECT_CAR", "PITSTOP"):
                self.tick_particles()
            self.draw()
            self.present()
            self.clock.tick(FPS)

    def present(self):
        ox = oy = 0
        if self.shake > 0.6:
            m = int(self.shake)
            ox, oy = random.randint(-m, m), random.randint(-m, m)
            self.shake *= 0.88
        else:
            self.shake = 0.0
        self.screen.fill(DARK)
        self.screen.blit(self.canvas, (ox, oy))
        kiosk_screen.flip()

    def handle_events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.quit()
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    self.quit()
                elif self.state == "SELECT_CAR":
                    if ev.key in (pygame.K_LEFT, pygame.K_a):
                        self.selected_car = (self.selected_car - 1) % 4
                    elif ev.key in (pygame.K_RIGHT, pygame.K_d):
                        self.selected_car = (self.selected_car + 1) % 4
                    elif ev.key == pygame.K_SPACE and self._car_unlocked(self.selected_car):
                        self._dismiss_golf_banner()
                        self.state = "PLAY"
                        self.reset()
                elif self.state == "PITSTOP":
                    n = len(PIT_ITEMS) + 1
                    if ev.key in (pygame.K_UP, pygame.K_LEFT, pygame.K_w, pygame.K_a):
                        self.pitstop_cursor = (self.pitstop_cursor - 1) % n
                        self.pitstop_msg = ""
                    elif ev.key in (pygame.K_DOWN, pygame.K_RIGHT, pygame.K_s, pygame.K_d):
                        self.pitstop_cursor = (self.pitstop_cursor + 1) % n
                        self.pitstop_msg = ""
                    elif ev.key == pygame.K_SPACE:
                        self._pitstop_confirm()
                elif ev.key == pygame.K_SPACE:
                    self._toggle()
                elif ev.key == pygame.K_r and self.state in ("OVER", "WIN"):
                    self.state = "SELECT_CAR"
                    self.selected_car = 0
            if kiosk_joy.is_action(ev):
                if self.state == "SELECT_CAR" and self._car_unlocked(self.selected_car):
                    self._dismiss_golf_banner()
                    self.state = "PLAY"
                    self.reset()
                elif self.state == "PITSTOP":
                    self._pitstop_confirm()
                elif self.state != "PLAY":
                    self._toggle()
        if self.state == "SELECT_CAR":
            if kiosk_joy.left():
                self.selected_car = (self.selected_car - 1) % 4
            if kiosk_joy.right():
                self.selected_car = (self.selected_car + 1) % 4
        elif self.state == "PITSTOP":
            n = len(PIT_ITEMS) + 1
            if self.pitstop_nav_cooldown > 0:
                self.pitstop_nav_cooldown -= 1
            elif kiosk_joy.up():
                self.pitstop_cursor = (self.pitstop_cursor - 1) % n
                self.pitstop_msg = ""
                self.pitstop_nav_cooldown = 12
            elif kiosk_joy.down():
                self.pitstop_cursor = (self.pitstop_cursor + 1) % n
                self.pitstop_msg = ""
                self.pitstop_nav_cooldown = 12

    def _toggle(self):
        if self.state == "PLAY":
            self.state = "PAUSE"
        elif self.state == "PAUSE":
            self.state = "PLAY"
        elif self.state in ("OVER", "WIN"):
            self.reset()

    def _pit_items(self):
        """PIT_ITEMS con i prezzi adattati all'auto scelta (self.selected_car)."""
        items = []
        for it in PIT_ITEMS:
            price = it["price"]
            if it["key"] == "super_shield":
                price = SUPER_SHIELD_PRICE_BY_CAR.get(self.selected_car, price)
            elif it["key"] == "extra_life":
                price = EXTRA_LIFE_PRICE_BY_CAR.get(self.selected_car, price)
            items.append({**it, "price": price})
        return items

    def _pitstop_confirm(self):
        """Conferma la voce selezionata nel menu pit stop: l'ultima voce e'
        sempre "Esci", le altre sono gli acquisti in PIT_ITEMS."""
        if self.pitstop_cursor >= len(PIT_ITEMS):
            self.shield_timer = max(self.shield_timer, PITSTOP_EXIT_SHIELD_FRAMES)
            self.state = "PLAY"
            return
        item = self._pit_items()[self.pitstop_cursor]
        if self.coins_got < item["price"]:
            self.pitstop_msg = "Monete insufficienti! ({}/{})".format(self.coins_got, item["price"])
            return
        self.coins_got -= item["price"]
        key = item["key"]
        if key == "super_shield":
            self.super_shield_timer = SUPER_SHIELD_FRAMES
        elif key == "triple_shot":
            self.triple_timer = TRIPLE_SHOT_FRAMES
            self.triple_fire_cooldown = 0
        elif key == "extra_life":
            self.lives += 1
        self.pitstop_msg = "{} acquistato!".format(item["name"])
        self.shield_timer = max(self.shield_timer, PITSTOP_EXIT_SHIELD_FRAMES)
        self.state = "PLAY"

    def update(self):
        if self.pitstop_entering:
            self._update_pitstop_entering()
            return
        keys = pygame.key.get_pressed()
        boost = keys[pygame.K_w] or keys[pygame.K_UP] or kiosk_joy.up() or kiosk_joy.action_held()
        if self.boost_timer > 0:
            self.boost_timer -= 1
        if self.shield_timer > 0:
            self.shield_timer -= 1
        if self.mitra_timer > 0:
            self.mitra_timer -= 1
        if self.super_shield_timer > 0:
            self.super_shield_timer -= 1
        if self.triple_timer > 0:
            self.triple_timer -= 1
        if self.hit_invuln > 0:
            self.hit_invuln -= 1

        # ondata aliena ("ORDA"): 15s di astronavi tra una citta' e l'altra,
        # niente auto nemiche/cantieri/pitstop finche' non finisce
        if self.horde_active:
            self.horde_timer -= 1
            if self.horde_timer <= 0:
                self.horde_active = False
                self.horde_ufos = []
                lo, hi = self._lane_bounds()
                self.enemies = [
                    self._new_enemy(random.uniform(lo, hi), -200.0 - i * 260)
                    for i in range(ENEMY_COUNT)
                ]

        current_segment = self.score // TOWN_EVERY
        if self.construction_mode:
            self.construction_timer -= 1
            if self.construction_timer <= 0:
                self.construction_mode = False
        else:
            self.construction_wait -= 1
            if (self.construction_wait <= 0 and not self.horde_active and
                    current_segment in CONSTRUCTION_SEGMENTS and
                    current_segment not in self.construction_segment_done):
                self.construction_segment_done.add(current_segment)
                self.construction_mode = True
                self.construction_side = random.choice(("left", "right"))
                self.construction_timer = CONSTRUCTION_DURATION
                self._filter_construction_zone()
                self.construction_wait = random.randint(CONSTRUCTION_MIN_WAIT, CONSTRUCTION_MAX_WAIT)

        # pit stop: ricompare a caso ogni 10-30 secondi
        if self.pitstop_active:
            self.pitstop_timer -= 1
            if self.pitstop_timer <= 0:
                self.pitstop_active = False
                self.pitstop_wait = random.randint(PITSTOP_WAIT_MIN, PITSTOP_WAIT_MAX)
        else:
            self.pitstop_wait -= 1
            if self.pitstop_wait <= 0 and not self.horde_active:
                self.pitstop_active = True
                self.pitstop_timer = PITSTOP_DURATION

        eff = self.speed + (BOOST_EXTRA if boost else 0.0)
        if self.boost_timer > 0:
            eff += self.speed * 0.25
        if self.mitra_timer > 0:
            eff *= MITRA_SPEED_BOOST
        if self.horde_active:
            eff *= HORDE_SPEED_MULT

        steer = PLAYER_STEER_SPEED * (0.45 if self.slip > 0 else 1.0)
        if keys[pygame.K_LEFT] or keys[pygame.K_a] or kiosk_joy.left():
            self.px -= steer
        if keys[pygame.K_RIGHT] or keys[pygame.K_d] or kiosk_joy.right():
            self.px += steer
        if self.slip > 0:
            self.slip -= 1
            self.px += math.sin(self.slip * 0.5) * 2.4      # skid sway
        lo, hi = self._lane_bounds()
        self.px = max(lo, min(self.px, hi))

        if self.pitstop_active and self.px < self.road_left:
            self.pitstop_active = False
            self.pitstop_wait = random.randint(PITSTOP_WAIT_MIN, PITSTOP_WAIT_MAX)
            self.pitstop_entering = True
            self.pitstop_enter_timer = PITSTOP_ENTER_FRAMES
            self.pitstop_target_x = self.road_left - PITSTOP_LANE_EXTRA / 2 - self.player_car_w / 2
            return

        self.scroll += eff
        pr = pygame.Rect(int(self.px), int(self.py), self.player_car_w, self.player_car_h)

        # fumo dallo scarico mentre acceleri
        if boost:
            self.smoke_cooldown -= 1
            if self.smoke_cooldown <= 0:
                self.smoke_cooldown = SMOKE_SPAWN_EVERY
                self.smoke.append({
                    "x": self.px + self.player_car_w / 2 + random.uniform(-4, 4),
                    "y": self.py + self.player_car_h - 4,
                    "vx": random.uniform(-0.6, 0.6),
                    "vy": random.uniform(0.6, 1.4),
                    "age": 0,
                })
        else:
            self.smoke_cooldown = 0

        # doppio sparo automatico mentre la mitra e' attiva
        if self.mitra_timer > 0:
            self.mitra_fire_cooldown -= 1
            if self.mitra_fire_cooldown <= 0:
                self.mitra_fire_cooldown = BULLET_FIRE_INTERVAL
                cx = self.px + CAR_W / 2
                self.bullets.append({"x": cx - BULLET_SIDE_OFFSET - BULLET_W / 2, "y": self.py, "kind": "mitra"})
                self.bullets.append({"x": cx + BULLET_SIDE_OFFSET - BULLET_W / 2, "y": self.py, "kind": "mitra"})

        # sparo triplo automatico (davanti + laterale) mentre e' attivo
        if self.triple_timer > 0:
            self.triple_fire_cooldown -= 1
            if self.triple_fire_cooldown <= 0:
                self.triple_fire_cooldown = BULLET_FIRE_INTERVAL
                cx = self.px + CAR_W / 2
                cy = self.py + CAR_H / 2
                self.bullets.append({"x": cx - BULLET_W / 2, "y": self.py, "kind": "triple_front"})
                self.bullets.append({"x": cx, "y": cy, "kind": "triple_side", "vx": -TRIPLE_SPEED})
                self.bullets.append({"x": cx, "y": cy, "kind": "triple_side", "vx": TRIPLE_SPEED})

        # proiettili: risalgono la strada (mitra/triple_front) o vanno di lato
        # (triple_side) e distruggono auto nemiche, l'asino o le pasticcerie
        for b in list(self.bullets):
            if b["kind"] == "triple_side":
                b["x"] += b["vx"]      # puramente orizzontale, niente scorrimento verticale
            else:
                b["y"] -= eff + BULLET_SPEED    # sempre piu' veloce dell'auto, mai al contrario
            if (b["y"] < -BULLET_H - 10 or b["y"] > WIN_H + 20 or
                    b["x"] < -BULLET_W - 20 or b["x"] > WIN_W + 20):
                self.bullets.remove(b)
                continue
            br = pygame.Rect(int(b["x"]), int(b["y"]), BULLET_W, BULLET_H)
            hit_something = False
            for e in self.enemies:
                er = pygame.Rect(int(e["x"]), int(e["y"]), CAR_W, CAR_H)
                if br.colliderect(er):
                    self.bullets.remove(b)
                    self.score += BULLET_SCORE
                    e["hp"] -= 1
                    if e["hp"] > 0:
                        self.popups.append({"x": e["x"] + CAR_W / 2, "y": e["y"],
                                            "txt": "+{} ({})".format(BULLET_SCORE, e["hp"]), "life": 35})
                    else:
                        self.popups.append({"x": e["x"] + CAR_W / 2, "y": e["y"],
                                            "txt": "+{}".format(BULLET_SCORE), "life": 35})
                        self._respawn_enemy(e)
                    hit_something = True
                    break
            if not hit_something and b in self.bullets and self.ufo is not None:
                ur = pygame.Rect(int(self.ufo["x"]), int(self.ufo["y"]), UFO_W, UFO_H)
                if br.colliderect(ur):
                    self.bullets.remove(b)
                    self.score += BULLET_SCORE
                    self.popups.append({"x": self.ufo["x"] + UFO_W / 2, "y": self.ufo["y"],
                                        "txt": "+{}".format(BULLET_SCORE), "life": 35})
                    self.ufo = None
                    self.ufo_wait = random.randint(UFO_WAIT_MIN, UFO_WAIT_MAX)
                    hit_something = True
            if not hit_something and b in self.bullets and self.horde_ufos:
                for u in list(self.horde_ufos):
                    ur = pygame.Rect(int(u["x"]), int(u["y"]), UFO_W, UFO_H)
                    if br.colliderect(ur):
                        self.bullets.remove(b)
                        self.score += BULLET_SCORE
                        self.popups.append({"x": u["x"] + UFO_W / 2, "y": u["y"],
                                            "txt": "+{}".format(BULLET_SCORE), "life": 35})
                        self.horde_ufos.remove(u)
                        hit_something = True
                        break
            if not hit_something and b in self.bullets and b["kind"] != "mitra" and self.pasticceria is not None:
                pr2 = pygame.Rect(int(self.pasticceria["x"]), int(self.pasticceria["y"]),
                                   PASTICCERIA_W, PASTICCERIA_H)
                if br.colliderect(pr2):
                    self.bullets.remove(b)
                    self.pasticceria["hp"] -= 1
                    if self.pasticceria["hp"] <= 0:
                        self.score += BULLET_SCORE
                        self.lives += 1
                        self.amor_timer = 150
                        self.popups.append({"x": self.pasticceria["x"] + PASTICCERIA_W / 2,
                                            "y": self.pasticceria["y"] + PASTICCERIA_H / 2,
                                            "txt": "PASTICCERIA DISTRUTTA! +{}".format(BULLET_SCORE), "life": 45})
                        self.pasticceria = None
                        self.pasticceria_wait = random.randint(PASTICCERIA_WAIT_MIN, PASTICCERIA_WAIT_MAX)
                    hit_something = True
            if hit_something or b not in self.bullets:
                continue
            if self.donkey is not None:
                dr = pygame.Rect(int(self.donkey["x"]), int(self.donkey["y"]), DONKEY_W, DONKEY_H)
                if br.colliderect(dr):
                    self.bullets.remove(b)
                    self.score += BULLET_SCORE
                    self.popups.append({"x": self.donkey["x"] + DONKEY_W / 2, "y": self.donkey["y"],
                                        "txt": "+{}".format(BULLET_SCORE), "life": 35})
                    self.donkey = None
                    self.donkey_wait = random.randint(DONKEY_WAIT_MIN, DONKEY_WAIT_MAX)

        # oncoming cars
        for e in self.enemies:
            e["y"] += eff
            er = pygame.Rect(int(e["x"]), int(e["y"]), CAR_W, CAR_H)
            if pr.colliderect(er) and self.hit_invuln <= 0:
                if self.super_shield_timer > 0 or (self.shield_timer > 0 and not e["armored"]):
                    self._respawn_enemy(e)
                    continue
                alive = self.begin_crash()
                self._respawn_enemy(e)
                if not alive:
                    return
                continue
            if not e["scored"] and e["y"] > self.py + CAR_H:
                if abs(e["x"] - self.px) < CAR_W + NEARMISS_GAP:
                    self.score += NEARMISS_BONUS
                    self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                        "txt": "+{}".format(NEARMISS_BONUS), "life": 45})
                e["scored"] = True
            if e["y"] > WIN_H + 20:
                self._respawn_enemy(e)

        # moto pazza contromano: arriva a caso, molto veloce, uccide se ti colpisce
        if self.moto is None:
            self.moto_wait -= 1
            if self.moto_wait <= 0:
                lo, hi = self._lane_bounds(MOTO_W)
                self.moto = {"x": random.uniform(lo, hi), "y": -MOTO_H - 10.0}
        else:
            self.moto["y"] += eff + MOTO_EXTRA_SPEED
            mr = pygame.Rect(int(self.moto["x"]), int(self.moto["y"]), MOTO_W, MOTO_H)
            if pr.colliderect(mr) and self.hit_invuln <= 0:
                if self.shield_timer > 0 or self.super_shield_timer > 0:
                    self.moto = None
                    self.moto_wait = random.randint(MOTO_WAIT_MIN, MOTO_WAIT_MAX)
                else:
                    alive = self.begin_crash()
                    self.moto = None
                    self.moto_wait = random.randint(MOTO_WAIT_MIN, MOTO_WAIT_MAX)
                    if not alive:
                        return
            elif self.moto["y"] > WIN_H + 20:
                self.moto = None
                self.moto_wait = random.randint(MOTO_WAIT_MIN, MOTO_WAIT_MAX)

        # asino grigio: attraversa la strada orizzontalmente solo tra Filattiera
        # e Villafranca (prima era anche prima di Borgotaro, e per un errore di
        # indice compariva un tratto troppo presto, tra Pontremoli e Filattiera)
        current_town = min(self.score // TOWN_EVERY + 1, len(TOWNS))
        in_donkey_zone = current_town == 5
        if self.donkey is None:
            if in_donkey_zone:
                self.donkey_wait -= 1
                if self.donkey_wait <= 0:
                    self.donkey = {"x": -DONKEY_W - 10.0, "y": -DONKEY_H - 20.0}
        else:
            self.donkey["x"] += DONKEY_SPEED
            if self.donkey["y"] < DONKEY_ROW_Y:
                self.donkey["y"] = min(DONKEY_ROW_Y, self.donkey["y"] + DONKEY_FALL_SPEED)
            dr = pygame.Rect(int(self.donkey["x"]), int(self.donkey["y"]), DONKEY_W, DONKEY_H)
            if pr.colliderect(dr) and self.hit_invuln <= 0:
                if self.shield_timer > 0 or self.super_shield_timer > 0:
                    self.donkey = None
                    self.donkey_wait = random.randint(DONKEY_WAIT_MIN, DONKEY_WAIT_MAX)
                else:
                    alive = self.begin_crash()
                    self.donkey = None
                    self.donkey_wait = random.randint(DONKEY_WAIT_MIN, DONKEY_WAIT_MAX)
                    if not alive:
                        return
            elif self.donkey["x"] > WIN_W + 10 or self.donkey["y"] > WIN_H + 20:
                self.donkey = None
                self.donkey_wait = random.randint(DONKEY_WAIT_MIN, DONKEY_WAIT_MAX)

        # pasticceria: puro sfondo decorativo sul bordo strada, scorre con la
        # strada come le altre scenografie - non collide mai col giocatore
        if self.pasticceria is None:
            self.pasticceria_wait -= 1
            if self.pasticceria_wait <= 0:
                side = random.choice(("left", "right"))
                if side == "left":
                    x = random.uniform(4, self.road_left - PASTICCERIA_W - 4)
                else:
                    x = random.uniform(self.road_right + 4, WIN_W - PASTICCERIA_W - 4)
                self.pasticceria = {"x": x, "y": -PASTICCERIA_H - 20.0, "hp": PASTICCERIA_HP}
        else:
            self.pasticceria["y"] += eff
            if self.pasticceria["y"] > WIN_H + 20:
                self.pasticceria = None
                self.pasticceria_wait = random.randint(PASTICCERIA_WAIT_MIN, PASTICCERIA_WAIT_MAX)

        # coins
        for c in self.coins:
            c["y"] += eff
            cr = pygame.Rect(int(c["x"]), int(c["y"]), COIN_R * 2, COIN_R * 2)
            if pr.colliderect(cr):
                bonus = int(round(COIN_BONUS * self.car_coin_mult))
                self.score += bonus
                self.coins_got += 1
                self.popups.append({"x": c["x"] + COIN_R, "y": c["y"],
                                    "txt": "+{}".format(bonus), "life": 40})
                self._recycle(c, COIN_R * 2, -260, -80)
                if not self.golf_unlocked:
                    self.lifetime_coins += 1
                    self._save_lifetime_coins()
                    if self.lifetime_coins >= GOLF_UNLOCK_COINS:
                        self.golf_unlocked = True
                        self.golf_newly_unlocked = True
                        self.unlock_timer = 150
                        self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                            "txt": "GOLF CABRIO SBLOCCATA!", "life": 60})
            elif c["y"] > WIN_H + 20:
                self._recycle(c, COIN_R * 2, -260, -80)

        # scudo: raccoglilo per diventare invincibile per qualche secondo
        for sh in self.shields:
            sh["y"] += eff
            shr = pygame.Rect(int(sh["x"]), int(sh["y"]), SHIELD_R * 2, SHIELD_R * 2)
            if pr.colliderect(shr):
                self.shield_timer = SHIELD_FRAMES
                self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                    "txt": "SCUDO!", "life": 40})
                self._recycle(sh, SHIELD_R * 2, -900, -500)
            elif sh["y"] > WIN_H + 20:
                self._recycle(sh, SHIELD_R * 2, -900, -500)

        # mitra doppia: raccoglila per velocita' doppia per 3 secondi
        for mi in self.mitras:
            mi["y"] += eff
            mir = pygame.Rect(int(mi["x"]), int(mi["y"]), MITRA_R * 2, MITRA_R * 2)
            if pr.colliderect(mir):
                self.mitra_timer = MITRA_FRAMES
                self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                    "txt": "MITRA DOPPIA!", "life": 40})
                self._recycle(mi, MITRA_R * 2, -1200, -700)
            elif mi["y"] > WIN_H + 20:
                self._recycle(mi, MITRA_R * 2, -1200, -700)

        # oil / water patches
        for p in self.puddles:
            p["y"] += eff
            prr = pygame.Rect(int(p["x"]), int(p["y"]) + 6, PUD_W, PUD_H - 12)
            if self.slip <= 0 and pr.colliderect(prr):
                self.slip = int(SLIP_FRAMES * self.car_slip_mult)
                self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                    "txt": "SBANDA!", "life": 40})
            if p["y"] > WIN_H + 40:
                self._recycle(p, PUD_W, -640, -180)

        # mothership aliena: attraversa lo schermo sempre da sinistra a destra
        if self.ufo is None:
            if not self.horde_active:
                self.ufo_wait -= 1
                if self.ufo_wait <= 0:
                    self.ufo = {"x": -UFO_W, "y": UFO_Y, "drop_in": MUSHROOM_DROP_EVERY}
        else:
            self.ufo["x"] += UFO_SPEED
            self.ufo["drop_in"] -= 1
            if self.ufo["drop_in"] <= 0:
                self.ufo["drop_in"] = MUSHROOM_DROP_EVERY
                kind = random.choice(("mushroom", "spike"))
                w = MUSHROOM_W if kind == "mushroom" else SPIKE_W
                self.mushrooms.append({
                    "x": self.ufo["x"] + UFO_W / 2 - w / 2,
                    "y": self.ufo["y"] + UFO_H,
                    "kind": kind,
                })
            if self.ufo["x"] > WIN_W:
                self.ufo = None
                self.ufo_wait = random.randint(UFO_WAIT_MIN, UFO_WAIT_MAX)

        # ondata: sciame di astronavi bidirezionale (sinistra->destra e viceversa)
        if self.horde_active:
            self.horde_ufo_wait -= 1
            if self.horde_ufo_wait <= 0 and len(self.horde_ufos) < HORDE_UFO_COUNT:
                self.horde_ufo_wait = random.randint(HORDE_UFO_WAIT_MIN, HORDE_UFO_WAIT_MAX)
                direction = random.choice(("ltr", "rtl"))
                self.horde_ufos.append({
                    "x": -UFO_W if direction == "ltr" else WIN_W,
                    "y": random.uniform(40, 96),
                    "speed": HORDE_UFO_SPEED if direction == "ltr" else -HORDE_UFO_SPEED,
                    "drop_in": HORDE_DROP_EVERY,
                })
            for u in list(self.horde_ufos):
                u["x"] += u["speed"]
                u["drop_in"] -= 1
                if u["drop_in"] <= 0:
                    u["drop_in"] = HORDE_DROP_EVERY
                    self.mushrooms.append({
                        "x": u["x"] + UFO_W / 2 - SPIKE_W / 2,
                        "y": u["y"] + UFO_H,
                        "kind": "spike",
                    })
                if u["x"] < -UFO_W - 10 or u["x"] > WIN_W + 10:
                    self.horde_ufos.remove(u)

        # funghetti / spikes lanciati dalla mothership
        for m in list(self.mushrooms):
            m["y"] += eff
            w = MUSHROOM_W if m["kind"] == "mushroom" else SPIKE_W
            h = MUSHROOM_H if m["kind"] == "mushroom" else SPIKE_H
            mr = pygame.Rect(int(m["x"]), int(m["y"]), w, h)
            if pr.colliderect(mr):
                self.mushrooms.remove(m)
                if m["kind"] == "mushroom":
                    self.boost_timer = MUSHROOM_BOOST_FRAMES
                    self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                        "txt": "FUNGHETTO! VIA!", "life": 40})
                elif self.shield_timer > 0 or self.super_shield_timer > 0:
                    self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                        "txt": "SCUDO!", "life": 40})
                elif self.hit_invuln > 0:
                    pass
                else:
                    if not self.begin_crash():
                        return
            elif m["y"] > WIN_H + 20:
                self.mushrooms.remove(m)

        # score, level, record
        self.score += 1 + int(0.4 * self.level)
        lvl = self.score // LEVEL_EVERY
        if lvl > self.level:
            self.level = lvl
            self.speed = (START_SPEED + SPEED_PER_LEVEL * self.level) * self.car_speed_mult
        if not self.beaten_record and self.start_max > 0 and self.score > self.start_max:
            self.celebrate_record()
        if self.score > self.max_score:
            self.max_score = self.score

        # cartelli delle citta' raggiunte, uno ogni TOWN_EVERY punti
        idx = min(self.score // TOWN_EVERY + 1, len(TOWNS))
        if idx > self.town_idx:
            self.town_idx = idx
            self.town_banner = {"txt": TOWNS[self.town_idx - 1], "life": TOWN_BANNER_FRAMES}
            if self.town_idx >= len(TOWNS):          # arrivati a Massa: fine del gioco
                self.state = "WIN"
                if self.score > self.max_score:
                    self.max_score = self.score
                self._save_hs()
                return
            elif self.town_idx > 1 and not self.horde_active:
                # tra una citta' e l'altra: ondata aliena (se una e' gia' in corso,
                # non la si "ricarica" - continua fino alla sua naturale scadenza)
                self.horde_active = True
                self.horde_timer = HORDE_DURATION
                self.construction_mode = False
                self.pitstop_active = False
                self.enemies = []

    def _update_pitstop_entering(self):
        """Breve frenata e parcheggio: il mondo rallenta fino a fermarsi e
        l'auto scivola dolcemente nel posto auto, poi si apre il menu."""
        self.pitstop_enter_timer -= 1
        progress = 1.0 - max(0, self.pitstop_enter_timer) / float(PITSTOP_ENTER_FRAMES)
        eff = self.speed * (1.0 - progress)      # rallenta fino a fermarsi
        self.scroll += eff
        self.px += (self.pitstop_target_x - self.px) * 0.12   # scivola verso il posto auto
        if self.pitstop_enter_timer <= 0:
            self.pitstop_entering = False
            self.pitstop_cursor = 0
            self.pitstop_msg = ""
            self.state = "PITSTOP"

    def begin_crash(self):
        self.lives -= 1
        if self.lives > 0:
            self.px = (self.road_left + self.road_right) / 2 - self.player_car_w / 2
            self.py = WIN_H - self.player_car_h - 24
            self.slip = 0
            self.hit_invuln = HIT_INVULN_FRAMES
            self.popups.append({"x": self.px + CAR_W / 2, "y": self.py - 6,
                                "txt": "VITE {}".format(self.lives), "life": 40})
            return True
        self.state = "CRASH"
        self.crash_timer = CRASH_FRAMES
        self.shake = 12.0
        self.crash_pos = (self.px, self.py)
        if self.score > self.max_score:
            self.max_score = self.score
        self._save_hs()
        return False

    def crash_step(self):
        self.crash_timer -= 1
        if self.crash_timer > CRASH_FRAMES - 10:
            self.shake = max(self.shake, self.crash_timer * 0.4)
        if self.crash_timer <= 0:
            self.state = "OVER"

    def celebrate_record(self):
        self.beaten_record = True
        self.record_timer = 150
        for _ in range(44):
            self.confetti.append({
                "x": random.uniform(0, WIN_W), "y": random.uniform(-60, -4),
                "vx": random.uniform(-1.4, 1.4), "vy": random.uniform(1.4, 4.2),
            })

    def tick_particles(self):
        for pop in self.popups:
            pop["y"] -= 1.3
            pop["life"] -= 1
        self.popups = [p for p in self.popups if p["life"] > 0]
        for f in self.confetti:
            f["x"] += f["vx"]
            f["y"] += f["vy"]
            f["vy"] += 0.14
        self.confetti = [f for f in self.confetti if f["y"] < WIN_H + 10]
        for sm in self.smoke:
            sm["x"] += sm["vx"]
            sm["y"] += sm["vy"]
            sm["age"] += 1
        self.smoke = [sm for sm in self.smoke if sm["age"] < SMOKE_LIFE]
        if self.record_timer > 0:
            self.record_timer -= 1
        if self.amor_timer > 0:
            self.amor_timer -= 1
        if self.unlock_timer > 0:
            self.unlock_timer -= 1
        if self.town_banner is not None:
            self.town_banner["life"] -= 1
            if self.town_banner["life"] <= 0:
                self.town_banner = None

    # ------------------------------------------------------------- drawing
    def draw(self):
        s = self.canvas

        byoff = int(self.scroll) % WIN_H
        s.blit(self.bg, (0, byoff - WIN_H))
        s.blit(self.bg, (0, byoff))

        pygame.draw.rect(s, DARK, (self.road_left, 0, ROAD_W, WIN_H))
        pygame.draw.rect(s, LITE, (self.road_left, 0, 4, WIN_H))
        pygame.draw.rect(s, LITE, (self.road_right - 4, 0, 4, WIN_H))

        if self.pitstop_active or self.pitstop_entering:   # PROTOTIPO: piazzola a sinistra
            pygame.draw.rect(s, DARK, (self.road_left - PITSTOP_LANE_EXTRA, 0, PITSTOP_LANE_EXTRA, WIN_H))
            pygame.draw.rect(s, BLUE, (self.road_left - PITSTOP_LANE_EXTRA, 0, 4, WIN_H))
            label = self.mid_font.render("PIT STOP", True, BLUE)
            s.blit(label, label.get_rect(center=(self.road_left - PITSTOP_LANE_EXTRA // 2, 70)))

        if self.pasticceria is not None:
            s.blit(self.pasticceria_img, (int(self.pasticceria["x"]), int(self.pasticceria["y"])))

        off = int(self.scroll) % 48
        for y in range(-48 + off, WIN_H, 48):
            pygame.draw.rect(s, LITE, (self.road_left + 10, y, 4, 16))
            pygame.draw.rect(s, LITE, (self.road_right - 14, y, 4, 16))

        coff = int(self.scroll) % 68
        cx = WIN_W // 2 - 3
        for y in range(-68 + coff, WIN_H, 68):
            pygame.draw.rect(s, LITE, (cx, y, 6, 34))

        if self.construction_mode:
            if self.construction_side == "left":
                cone_x = self.road_left + CONSTRUCTION_ROAD_W
            else:
                cone_x = self.road_right - CONSTRUCTION_ROAD_W
            coff = int(self.scroll) % 40
            for y in range(-40 + coff, WIN_H, 40):
                pygame.draw.rect(s, (255, 0, 0), (cone_x - 8, y, 16, 28))
                pygame.draw.polygon(s, (200, 0, 0), [(cone_x - 8, y), (cone_x + 8, y), (cone_x, y - 8)])

        for p in self.puddles:
            s.blit(self.puddle_img, (int(p["x"]), int(p["y"])))
        for c in self.coins:
            s.blit(self.coin_img, (int(c["x"]), int(c["y"])))
        for sh in self.shields:
            s.blit(self.shield_img, (int(sh["x"]), int(sh["y"])))
        for mi in self.mitras:
            s.blit(self.mitra_img, (int(mi["x"]), int(mi["y"])))
        for b in self.bullets:
            pygame.draw.rect(s, PROGRESS_DOT, (int(b["x"]), int(b["y"]), BULLET_W, BULLET_H))
        for e in self.enemies:
            img = self.enemy_img_armored if e["armored"] else self.enemy_img
            s.blit(img, (int(e["x"]), int(e["y"])))
        if self.moto is not None:
            s.blit(self.moto_img, (int(self.moto["x"]), int(self.moto["y"])))
        if self.donkey is not None:
            s.blit(self.donkey_img, (int(self.donkey["x"]), int(self.donkey["y"])))
        if self.ufo is not None:
            s.blit(self.ufo_img, (int(self.ufo["x"]), int(self.ufo["y"])))
        for u in self.horde_ufos:
            s.blit(self.ufo_img, (int(u["x"]), int(u["y"])))
        for m in self.mushrooms:
            img = self.mushroom_img if m["kind"] == "mushroom" else self.spike_img
            s.blit(img, (int(m["x"]), int(m["y"])))

        for sm in self.smoke:
            t = sm["age"] / float(SMOKE_LIFE)
            r = int(SMOKE_R0 + (SMOKE_R1 - SMOKE_R0) * t)
            if r > 0:
                pygame.draw.circle(s, GREY, (int(sm["x"]), int(sm["y"])), r, 1)

        if self.state == "CRASH":
            self._draw_wreck(s, *self.crash_pos)
        else:
            if self.hit_invuln <= 0 or (self.hit_invuln // 4) % 2 == 0:
                s.blit(self.player_img, (int(self.px), int(self.py)))
            if self.shield_timer > 0:
                pulse = 3 if (self.shield_timer // 4) % 2 == 0 else 1
                cx, cy = int(self.px + self.player_car_w / 2), int(self.py + self.player_car_h / 2)
                pygame.draw.circle(s, LITE, (cx, cy), self.player_car_h // 2 + 8, pulse)
            if self.super_shield_timer > 0:
                pulse = 3 if (self.super_shield_timer // 4) % 2 == 0 else 1
                cx, cy = int(self.px + self.player_car_w / 2), int(self.py + self.player_car_h / 2)
                pygame.draw.circle(s, BLUE, (cx, cy), self.player_car_h // 2 + 12, pulse)

        for pop in self.popups:
            if pop["life"] % 6 != 1:                       # slight flicker as it fades
                r = self.pop_font.render(pop["txt"], True, LITE)
                s.blit(r, r.get_rect(center=(int(pop["x"]), int(pop["y"]))))
        for f in self.confetti:
            pygame.draw.rect(s, LITE, (int(f["x"]), int(f["y"]), 3, 3))

        self._draw_progress(s)

        if self.construction_mode:
            self._draw_construction_sign(s)

        s.blit(self.hud_font.render("PUNTI {}".format(self.score), True, LITE), (14, 12))
        s.blit(self.hud_font.render("RECORD {}".format(self.max_score), True, LITE), (14, 40))
        s.blit(self.hud_font.render("LIV {}".format(self.level + 1), True, LITE), (14, 68))
        s.blit(self.hud_font.render("MONETE {}".format(self.coins_got), True, LITE), (14, 96))
        s.blit(self.hud_font.render("VITE {}".format(self.lives), True, LITE), (14, 124))
        if self.shield_timer > 0:
            sec_left = self.shield_timer // FPS + 1
            s.blit(self.hud_font.render("SCUDO {}".format(sec_left), True, LITE), (14, 152))
        if self.mitra_timer > 0:
            sec_left = self.mitra_timer // FPS + 1
            s.blit(self.hud_font.render("MITRA {}".format(sec_left), True, LITE), (14, 152))
        if self.super_shield_timer > 0:
            sec_left = self.super_shield_timer // FPS + 1
            s.blit(self.hud_font.render("SUPER SCUDO {}".format(sec_left), True, BLUE), (14, 180))
        if self.triple_timer > 0:
            sec_left = self.triple_timer // FPS + 1
            s.blit(self.hud_font.render("SPARO TRIPLO {}".format(sec_left), True, PROGRESS_DOT), (14, 180))
        if not self.golf_unlocked:
            missing = max(0, GOLF_UNLOCK_COINS - self.lifetime_coins)
            s.blit(self.progress_font.render(
                "GOLF CABRIO: -{} monete".format(missing), True, LITE), (14, 208))

        if self.record_timer > 0 and (self.record_timer // 6) % 2 == 0:
            r = self.mid_font.render("NUOVO RECORD!", True, LITE)
            s.blit(r, r.get_rect(center=(WIN_W // 2, 40)))

        if self.amor_timer > 0 and (self.amor_timer // 6) % 2 == 0:
            a = self.big_font.render("AMOR", True, PROGRESS_DOT)
            s.blit(a, a.get_rect(center=(WIN_W // 2, WIN_H // 2 - 60)))

        if self.unlock_timer > 0 and (self.unlock_timer // 6) % 2 == 0:
            u = self.mid_font.render("GOLF CABRIO SBLOCCATA!", True, LITE)
            s.blit(u, u.get_rect(center=(WIN_W // 2, 40)))

        if self.horde_active and (self.anim_frame // 6) % 2 == 0:
            o = self.big_font.render("ORDA!", True, PROGRESS_DOT)
            s.blit(o, o.get_rect(center=(WIN_W // 2, 40)))

        if self.town_banner is not None:
            self._draw_sign(s, self.town_banner["txt"])

        if self.state == "CRASH":
            flash = max(0, self.crash_timer - (CRASH_FRAMES - 8)) / 8.0
            if flash > 0:
                veil = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
                veil.fill((255, 255, 255, int(210 * flash)))
                s.blit(veil, (0, 0))
        elif self.state == "PAUSE":
            if kiosk_joy.has_stick():
                self._overlay("PAUSA", [
                    "Sinistra / Destra:  stick o croce direzionale",
                    "Accelera:  su, o tieni premuto un tasto",
                    "Monete = punti bonus, sorpassi stretti = +50",
                    "Scudo raccolto = 5 secondi invincibile",
                    "Esci:  tieni premuti 2 tasti insieme",
                    "",
                    "Premi un tasto per continuare",
                ])
            else:
                self._overlay("PAUSA", [
                    "Sinistra / Destra:  frecce o A / D",
                    "Accelera:  W o freccia su",
                    "Monete = punti bonus, sorpassi stretti = +50",
                    "Scudo raccolto = 5 secondi invincibile",
                    "Pausa:  barra spaziatrice     Esci:  ESC o Q",
                    "",
                    "Premi SPAZIO per continuare",
                ])
        elif self.state == "PITSTOP":
            self._draw_pitstop_menu(s)
        elif self.state == "OVER":
            lines = ["Punteggio:  {}".format(self.score),
                     "Record:  {}".format(self.max_score),
                     "Monete raccolte:  {}".format(self.coins_got), ""]
            if self.beaten_record:
                lines.append("NUOVO RECORD!")
            if kiosk_joy.has_stick():
                lines.append("Premi un tasto = ricomincia      2 insieme = esci")
            else:
                lines.append("SPAZIO o R = ricomincia      ESC = esci")
            self._overlay("HAI PERSO", lines)
            if self.beaten_record:
                self._draw_medal(s, WIN_W // 2, 130)
        elif self.state == "WIN":
            lines = ["Sei arrivato a Massa!",
                     "Punteggio:  {}".format(self.score),
                     "Record:  {}".format(self.max_score),
                     "Monete raccolte:  {}".format(self.coins_got), ""]
            if self.beaten_record:
                lines.append("NUOVO RECORD!")
            if kiosk_joy.has_stick():
                lines.append("Premi un tasto = ricomincia      2 insieme = esci")
            else:
                lines.append("SPAZIO o R = ricomincia      ESC = esci")
            self._overlay("HAI VINTO!", lines)
            self._draw_medal(s, WIN_W // 2, 130)
        elif self.state == "SELECT_CAR":
            self._draw_car_selection(s)

        kiosk_joy.blit_exit_hint(s)
        self.anim_frame += 1

    def _draw_progress(self, s):
        """Barra laterale col percorso: una tacca per ogni tappa e un puntino
        rosso che mostra dove si trova l'auto lungo il tragitto."""
        x = self.road_right + 30
        top, bottom = 50, WIN_H - 50
        pygame.draw.line(s, LITE, (x, top), (x, bottom), 2)
        total = TOWN_EVERY * len(TOWNS)
        for i, name in enumerate(TOWNS):
            ty = top + (bottom - top) * i / (len(TOWNS) - 1)
            pygame.draw.line(s, LITE, (x - 5, int(ty)), (x + 5, int(ty)), 2)
            label = self.progress_font.render(name, True, LITE)
            s.blit(label, (x + 9, int(ty) - label.get_height() // 2))
        frac = min(1.0, self.score / float(total))
        py = top + (bottom - top) * frac
        pygame.draw.circle(s, PROGRESS_DOT, (x, int(py)), 6)

    def _draw_wreck(self, s, x, y):
        pygame.draw.rect(s, LITE, (x + 2, y + 8, CAR_W - 4, CAR_H - 16))
        pygame.draw.line(s, DARK, (x + 4, y + 10), (x + CAR_W - 4, y + CAR_H - 10), 3)
        pygame.draw.line(s, DARK, (x + CAR_W - 4, y + 10), (x + 4, y + CAR_H - 10), 3)
        for dx, dy in ((-9, 6), (CAR_W + 4, 12), (7, CAR_H - 2), (CAR_W - 12, -7)):
            pygame.draw.rect(s, LITE, (x + dx, y + dy, 4, 4))

    def _draw_sign(self, s, name):
        txt = self.mid_font.render(name, True, DARK)
        w = txt.get_width() + 40
        h = txt.get_height() + 22
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (WIN_W // 2, 150)
        pygame.draw.rect(s, LITE, rect)
        pygame.draw.rect(s, DARK, rect, 3)
        s.blit(txt, txt.get_rect(center=rect.center))

    def _draw_medal(self, s, cx, cy):
        pygame.draw.circle(s, LITE, (cx, cy), 24)
        pygame.draw.circle(s, DARK, (cx, cy), 24, 3)
        pygame.draw.polygon(s, DARK, _star_points(cx, cy, 13))

    def _overlay(self, title, lines):
        s = self.canvas
        veil = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        veil.fill((13, 13, 18, 222))
        s.blit(veil, (0, 0))
        t = self.big_font.render(title, True, LITE)
        s.blit(t, t.get_rect(center=(WIN_W // 2, 220)))
        y = 310
        for ln in lines:
            if ln:
                r = self.mid_font.render(ln, True, LITE)
                s.blit(r, r.get_rect(center=(WIN_W // 2, y)))
            y += 40

    def _draw_pitstop_menu(self, s):
        """Menu del pit stop: lista acquisti con prezzo, cursore, e voce
        finale per uscire. Naviga con su/giu (o stick), conferma con SPAZIO
        (o un tasto)."""
        veil = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        veil.fill((13, 13, 18, 222))
        s.blit(veil, (0, 0))

        t = self.big_font.render("PIT STOP", True, BLUE)
        s.blit(t, t.get_rect(center=(WIN_W // 2, 130)))

        coins_txt = self.mid_font.render("Monete: {}".format(self.coins_got), True, LITE)
        s.blit(coins_txt, coins_txt.get_rect(center=(WIN_W // 2, 190)))

        rows = [(it["name"], it["price"], it["desc"]) for it in self._pit_items()] + [("Esci", None, "")]
        y = 250
        for i, (name, price, desc) in enumerate(rows):
            selected = i == self.pitstop_cursor
            color = BLUE if selected else LITE
            label = "{}{}".format(name, "  -  {} monete".format(price) if price is not None else "")
            if selected:
                label = "> " + label
            row = self.mid_font.render(label, True, color)
            s.blit(row, row.get_rect(center=(WIN_W // 2, y)))
            if desc and selected:
                d = self.progress_font.render(desc, True, GREY)
                s.blit(d, d.get_rect(center=(WIN_W // 2, y + 22)))
            y += 56

        if self.pitstop_msg:
            m = self.mid_font.render(self.pitstop_msg, True, PROGRESS_DOT)
            s.blit(m, m.get_rect(center=(WIN_W // 2, y + 10)))

        hint = "Su/Giu: scegli   Un tasto: conferma" if kiosk_joy.has_stick() else \
               "Su/Giu: scegli   SPAZIO: conferma"
        hint_r = self.progress_font.render(hint, True, GREY)
        s.blit(hint_r, hint_r.get_rect(center=(WIN_W // 2, WIN_H - 40)))

    def _draw_construction_sign(self, s):
        """Cartello di allerta lampeggiante per cantiere con strada ristretta:
        triangolo con punto esclamativo (ci sta sempre) + banner largo quanto
        serve per il testo (prima il testo era schiacciato dentro il triangolo
        stretto e finiva illeggibile fuori dai bordi)."""
        if (self.construction_timer // 8) % 2 != 0:
            return
        size = 34
        cx, cy = WIN_W // 2, 44
        pts = [(cx, cy - size), (cx + size, cy + size), (cx - size, cy + size)]
        pygame.draw.polygon(s, (255, 200, 0), pts)
        pygame.draw.polygon(s, (200, 100, 0), pts, 3)
        excl = self.mid_font.render("!", True, (0, 0, 0))
        s.blit(excl, excl.get_rect(center=(cx, cy + 8)))

        txt = self.mid_font.render("LAVORI IN CORSO", True, DARK)
        w, h = txt.get_width() + 36, txt.get_height() + 16
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (cx, cy + size + 10 + h // 2)
        pygame.draw.rect(s, (255, 200, 0), rect)
        pygame.draw.rect(s, (200, 100, 0), rect, 3)
        s.blit(txt, txt.get_rect(center=rect.center))

    def _draw_car_selection(self, s):
        veil = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        veil.fill((13, 13, 18, 220))
        s.blit(veil, (0, 0))

        logo_center = (WIN_W // 2, 82)
        shimmer = (self.anim_frame // 2) % 6
        if shimmer < 5:
            offset_x = [0, 2, -2, 1, -1][shimmer]
            offset_y = [0, 1, -1, 2, 1][shimmer]
            shadow = _render_pixel_text(self.logo_font, "Cisa Race", PROGRESS_DOT)
            s.blit(shadow, shadow.get_rect(center=(logo_center[0] + 6 + offset_x, logo_center[1] + 6 + offset_y)))
        logo = _render_pixel_text(self.logo_font, "Cisa Race", WHITE)
        s.blit(logo, logo.get_rect(center=logo_center))

        title = self.mid_font.render("SCEGLI L'AUTO", True, LITE)
        s.blit(title, title.get_rect(center=(WIN_W // 2, 152)))
        if self.golf_newly_unlocked and (self.anim_frame // 6) % 2 == 0:
            banner = self.mid_font.render("GOLF CABRIO SBLOCCATA!", True, PROGRESS_DOT)
            s.blit(banner, banner.get_rect(center=(WIN_W // 2, 178)))
        car_y = 200
        slots = [WIN_W // 8, 3 * WIN_W // 8, 5 * WIN_W // 8, 7 * WIN_W // 8]
        cars = [
            (self.player_img_beetle, "MAGGIOLINO", "+10% velocita'", CAR_W, CAR_H, True),
            (self.player_car_bmw, "BMW Z3", "meno slittamento", CAR_W, CAR_H, True),
            (self.player_car_volvo, "VOLVO SW", "-5% vel, +1 vita", VOLVO_W, VOLVO_H, True),
            (self.player_car_golf, "GOLF CABRIO", "+20% monete", CAR_W, CAR_H, self.golf_unlocked),
        ]
        for i, (img, name, perk, cw, ch, unlocked) in enumerate(cars):
            cx = slots[i]
            cy = car_y - (ch - CAR_H) // 2
            color = LITE if self.selected_car == i else DARK
            if unlocked:
                s.blit(img, (cx - cw // 2, cy))
            else:
                shadow_car = img.copy()
                shadow_car.fill((70, 70, 70, 255), special_flags=pygame.BLEND_RGBA_MULT)
                s.blit(shadow_car, (cx - cw // 2, cy))
            name_txt = self.mid_font.render(name, True, color)
            s.blit(name_txt, name_txt.get_rect(center=(cx, car_y + CAR_H + 30)))
            if unlocked:
                perk_txt = self.progress_font.render(perk, True, color)
            else:
                perk_txt = self.progress_font.render(
                    "{}/{} MONETE".format(self.lifetime_coins, GOLF_UNLOCK_COINS), True, color)
            s.blit(perk_txt, perk_txt.get_rect(center=(cx, car_y + CAR_H + 52)))
            if self.selected_car == i:
                pygame.draw.rect(s, LITE, (cx - cw // 2 - 12, cy - 10, cw + 24, ch + 20), 3)
        if kiosk_joy.has_stick():
            instr_txt = "Stick: scegli     Premi un tasto: gioca"
        else:
            instr_txt = "Frecce/A-D: scegli     SPAZIO: gioca"
        instr = self.mid_font.render(instr_txt, True, LITE)
        s.blit(instr, instr.get_rect(center=(WIN_W // 2, WIN_H - 80)))

    @staticmethod
    def quit():
        pygame.quit()
        sys_exit()


if __name__ == "__main__":
    Race().run()
