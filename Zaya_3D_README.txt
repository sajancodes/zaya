Zaya 3D (Blender) - as-is 2D identity
=====================================
File: Zaya_3D.blend (Blender 5.2)

Approach: each 2D mode is an image plane textured with the EXACT original PNG
(no repainting, no pixel changes). Modes are separate objects:
  Zaya_standby, Zaya_neutral, Zaya_happy, Zaya_sad, Zaya_angry,
  Zaya_surprised, Zaya_poked, Zaya_thinking

Usage:
- In the Outliner, toggle eye (visibility) of the mode you want.
- Only one plane should be visible at a time for a clean render.
- A demo animation cycles all modes (frames 1..240). Scrub the timeline.
- Camera is front-facing so the artwork matches the 2D identity 1:1.

Notes:
- Transparent areas use the original PNG alpha channel (BLEND).
- Do not scale/rotate the planes if you want pixel-perfect identity.
- To add real 3D depth later, duplicate a plane and displace, but that
  will deviate from the original 2D pixels.
