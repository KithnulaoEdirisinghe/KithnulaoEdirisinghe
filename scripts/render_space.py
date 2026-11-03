#!/usr/bin/env python3
"""Renders the static space imagery in assets/render/ (run once; the results are committed).

- gargantua.jpg  ray-traced black hole for the header: photons are bent around a
                 Schwarzschild black hole, so the accretion disk is lensed into the
                 halo over and under the shadow and background stars are distorted.
- space.jpg      a tall warm starfield/dust texture the other panels are cut from.

    python scripts/render_space.py
Needs numpy and Pillow.
"""
import os

import numpy as np
from PIL import Image, ImageFilter

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets", "render")
rng = np.random.default_rng(7)

# colours of the disk from cool outer edge to white-hot inner edge (linear-ish RGB)
DISK_RAMP = np.array([
    [0.10, 0.04, 0.015],
    [0.42, 0.17, 0.05],
    [0.88, 0.48, 0.18],
    [1.00, 0.80, 0.55],
    [1.00, 0.95, 0.86],
], dtype=np.float32)


def ramp(t):
    t = np.clip(t, 0, 1) * (len(DISK_RAMP) - 1)
    i = np.minimum(t.astype(int), len(DISK_RAMP) - 2)
    f = (t - i)[..., None]
    return DISK_RAMP[i] * (1 - f) + DISK_RAMP[i + 1] * f


def star_map(w, h, count, seed):
    """Equirectangular star field: soft points with a range of brightness and slight colour."""
    r = np.random.default_rng(seed)
    img = np.zeros((h, w, 3), np.float32)
    ys, xs = r.integers(0, h, count), r.integers(0, w, count)
    mag = r.pareto(2.2, count).astype(np.float32) * 0.18 + 0.03
    tint = np.stack([np.ones(count), 0.85 + 0.15 * r.random(count), 0.7 + 0.3 * r.random(count)], 1).astype(np.float32)
    np.add.at(img, (ys, xs), tint * mag[:, None])
    glow = np.asarray(Image.fromarray(np.clip(img * 255, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(1.2)),
                      np.float32) / 255
    return np.clip(img * 0.6 + glow * 2.4, 0, 4)


def fbm(shape, octaves, seed, scale=1.0):
    """Smooth fractal noise by summing upsampled random grids."""
    r = np.random.default_rng(seed)
    h, w = shape
    out = np.zeros(shape, np.float32)
    amp, total = 1.0, 0.0
    for o in range(octaves):
        gh, gw = max(2, int(h / (scale * 2 ** (octaves - o)))), max(2, int(w / (scale * 2 ** (octaves - o))))
        grid = Image.fromarray((r.random((gh, gw)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
        out += amp * np.asarray(grid, np.float32) / 255
        total += amp
        amp *= 0.55
    return out / total


def render_black_hole(W, H, bh_x=0.70, bh_y=0.47, dist=19.0, incl_deg=6.0, half_fov=0.46, roll_deg=-9.0):
    """Schwarzschild ray tracer (units of the Schwarzschild radius)."""
    stars = star_map(4096, 2048, 26000, 3)
    cam = np.array([0, dist * np.sin(np.radians(incl_deg)), -dist * np.cos(np.radians(incl_deg))], np.float32)
    fwd = -cam / np.linalg.norm(cam)
    right = np.cross(fwd, [0, 1, 0]).astype(np.float32)
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    c, s_ = np.cos(np.radians(roll_deg)), np.sin(np.radians(roll_deg))
    right, up = right * c + up * s_, up * c - right * s_

    xs = (np.arange(W, dtype=np.float32) + 0.5 - bh_x * W) / (H / 2)
    ys = -(np.arange(H, dtype=np.float32) + 0.5 - bh_y * H) / (H / 2)
    gx, gy = np.meshgrid(xs, ys)
    d = fwd + (gx[..., None] * right + gy[..., None] * up) * half_fov
    d /= np.linalg.norm(d, axis=-1, keepdims=True)
    n = W * H
    pos = np.broadcast_to(cam, (n, 3)).copy()
    vel = d.reshape(n, 3).copy()
    h2 = np.sum(np.cross(pos, vel) ** 2, axis=1)

    col = np.zeros((n, 3), np.float32)
    alpha = np.zeros(n, np.float32)
    alive = np.ones(n, bool)
    # disk texture: fine rings in log radius, broken up along the orbit
    ring_f = rng.uniform(12, 160, 28)
    ring_p = rng.uniform(0, 2 * np.pi, 28)
    ring_m = rng.integers(1, 6, 28)
    ring_q = rng.uniform(0, 2 * np.pi, 28)

    for step in range(900):
        idx = np.nonzero(alive)[0]
        if idx.size == 0:
            break
        p, v = pos[idx], vel[idx]
        r = np.linalg.norm(p, axis=1)
        dt = np.clip(0.06 * r, 0.025, 0.9)[:, None]
        acc = -1.5 * h2[idx, None] * p / (r ** 5)[:, None]
        v2 = v + acc * dt
        p2 = p + v2 * dt
        # accretion disk in the y=0 plane
        cross = (p[:, 1] * p2[:, 1]) < 0
        if cross.any():
            c = np.nonzero(cross)[0]
            t = (p[c, 1] / (p[c, 1] - p2[c, 1]))[:, None]
            hit = p[c] + (p2[c] - p[c]) * t
            rc = np.linalg.norm(hit, axis=1)
            ok = (rc > 3.0) & (rc < 15.0)
            if ok.any():
                c, hit, rc = c[ok], hit[ok], rc[ok]
                phi = np.arctan2(hit[:, 2], hit[:, 0])
                lr = np.log(rc)
                tex = np.zeros_like(rc)
                for f, ph, m, q in zip(ring_f, ring_p, ring_m, ring_q):
                    tex += np.sin(f * lr + ph + 0.35 * np.sin(m * phi + q))
                tex = (0.8 + 0.2 * np.tanh(tex / 4)) * (0.85 + 0.15 * np.sin(97 * lr + 9 * phi) * np.sin(61 * lr - 5 * phi))
                heat = (rc / 3.0) ** -1.6 * np.sqrt(np.clip(1 - np.sqrt(3.0 / rc), 0, 1)) * 4.2
                # relativistic beaming: emitter orbits counter-clockwise seen from +y
                vorb = np.sqrt(0.5 / (rc - 1.0))
                tang = np.stack([-hit[:, 2], np.zeros_like(rc), hit[:, 0]], 1) / rc[:, None]
                nd = -v[c] / np.linalg.norm(v[c], axis=1, keepdims=True)
                g = 1 / (np.sqrt(1 - vorb ** 2) * (1 - vorb * np.sum(tang * nd, 1)))
                beam = 1 + 0.55 * (g ** 3 - 1)
                bright = heat * tex * np.clip(beam, 0.25, 3)
                a = np.clip(bright * 2.2, 0, 0.97) * np.clip((15 - rc) / 7, 0, 1) ** 1.5
                emit = ramp(np.clip(bright * 0.7, 0, 1)) * (0.7 + 1.3 * bright)[:, None]
                gi = idx[c]
                col[gi] += ((1 - alpha[gi]) * a)[:, None] * emit
                alpha[gi] += (1 - alpha[gi]) * a
        pos[idx], vel[idx] = p2, v2
        r2 = np.linalg.norm(p2, axis=1)
        fell = r2 < 1.0
        escaped = (r2 > 45) & (np.sum(p2 * v2, 1) > 0)
        opaque = alpha[idx] > 0.985
        alive[idx[fell | escaped | opaque]] = False
        if escaped.any():
            e = idx[escaped]
            dirs = vel[e] / np.linalg.norm(vel[e], axis=1, keepdims=True)
            u = ((np.arctan2(dirs[:, 2], dirs[:, 0]) / (2 * np.pi) + 0.5) * (stars.shape[1] - 1)).astype(int)
            w = ((np.arccos(np.clip(dirs[:, 1], -1, 1)) / np.pi) * (stars.shape[0] - 1)).astype(int)
            col[e] += ((1 - alpha[e]) * 0.9)[:, None] * stars[w, u]
    return col.reshape(H, W, 3)


def finish(img, bloom=True, grain=0.012, seed=1):
    """Bloom, filmic tone curve, warm grade, grain; returns 8-bit RGB."""
    if bloom:
        bright = np.clip(img - 0.55, 0, None)
        b8 = Image.fromarray(np.clip(bright * 255 / 3, 0, 255).astype(np.uint8))
        for radius, k in ((6, 0.9), (22, 0.7), (60, 0.5)):
            img = img + k * 3 * np.asarray(b8.filter(ImageFilter.GaussianBlur(radius)), np.float32) / 255
    x = img * 1.05
    img = (x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14)  # ACES fit
    img = img * np.array([1.0, 0.93, 0.84], np.float32)  # warm grade
    img += np.random.default_rng(seed).normal(0, grain, img.shape).astype(np.float32)
    return (np.clip(img, 0, 1) ** (1 / 1.05) * 255).astype(np.uint8)


def add_planet(img, cx, cy, r, light_x):
    """A small dark planet with a thin warm rim facing the disk (like Miller's planet)."""
    h, w, _ = img.shape
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = (x - cx) / r, (y - cy) / r
    d2 = dx ** 2 + dy ** 2
    inside = d2 < 1
    nz = np.sqrt(np.clip(1 - d2, 0, 1))
    lit = np.clip(dx * light_x * 0.9 + nz * 0.15, 0, 1) ** 2.2
    shade = np.stack([lit * 0.9, lit * 0.55, lit * 0.3], -1) * 255
    edge = np.clip((1 - np.sqrt(d2)) * r, 0, 1)[..., None]
    img[inside] = (img[inside] * (1 - edge[inside]) + shade[inside] * edge[inside]).astype(np.uint8)
    return img


def render_space(W, H):
    """Warm dusty deep-space texture with a dense, faint starfield."""
    dust = fbm((H, W), 7, 11, scale=0.6) ** 2.4
    lanes = fbm((H, W), 6, 23, scale=0.5)
    base = np.stack([dust * 0.13, dust * 0.075, dust * 0.04], -1) * (0.6 + 0.8 * lanes[..., None])
    stars = star_map(W, H, int(W * H / 140), 5)
    img = base + stars * 0.9
    return finish(img.astype(np.float32), bloom=False, grain=0.01, seed=2)


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    W, H = 1800, 600
    bh = render_black_hole(W * 2, H * 2)
    bh = bh.reshape(H, 2, W, 2, 3).mean(axis=(1, 3))  # 2x2 supersampling
    img = finish(bh)
    img = add_planet(img, int(W * 0.47), int(H * 0.31), 7, light_x=1)
    Image.fromarray(img).save(os.path.join(OUT, "gargantua.jpg"), quality=86, optimize=True, progressive=True)
    Image.fromarray(render_space(1200, 2000)).save(os.path.join(OUT, "space.jpg"), quality=82, optimize=True,
                                                   progressive=True)
    print("rendered gargantua.jpg and space.jpg")
