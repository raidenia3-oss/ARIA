# Why Each Rule Works

The copy-ready prompt is in the [README](./README.md). This document explains *why* each rule is specified the way it is: so you can make informed adjustments for your project, and so the AI produces better output when it understands the reasoning behind each constraint.

---

## Rule 1 · The 3-Tier Glass System

**Why three named tiers instead of free values?**

When blur and opacity values are chosen freely, the eye can't distinguish foreground from background. Three fixed tiers: 60px / 30px / 16px: create reliable visual distance. The gap between panel and card feels like depth. Without named tiers, generated output tends to cluster at 20–30px and flatten out.

**Why these exact values?**

- 60px on a full-panel overlay is enough to separate the content layer from the video without destroying the background entirely. Below ~40px, text becomes hard to read over dynamic backgrounds.
- 30px on cards inside panels creates secondary depth: they read as objects resting *on* the panel.
- 16px on pills and buttons is just enough to catch the blur effect on the glass edge without blurring behind the pill text.

**Why `saturate(180%)`?**

The saturation boost prevents the background colors from washing out behind the dark overlay. Without it, blurred glass panels tend to look grey and muddy instead of deep and rich.

---

## Rule 2 · The XOR Border Trick

**Why not `border: 1px solid rgba(255,255,255,0.2)`?**

A uniform border is flat: the same intensity on all four sides. Physical glass doesn't behave this way. Light hits the top-left edge and wraps around, fading toward the bottom-right. The XOR mask technique creates a border from a gradient, which matches that physical behavior.

**How the mask works:**

The `::before` element covers the full element. Setting `padding: 1px` means the *content box* is 1px smaller than the *border box*. The XOR mask says: *show where the two mask layers do NOT overlap*, which is precisely the 1px padding strip. Result: a gradient rendered only along the border edge, with zero `border` properties involved.

```
Full box:     ████████████
Content box:  ██░░░░░░░░██   (1px inset)
XOR result:   ░░░░░░░░░░░░   (only the strip)
              ↑↑↑↑↑↑↑↑↑↑↑↑  gradient rendered here
```

The gradient angle (160deg) points from top-left to bottom-right, mimicking a light source in the top-left corner. This is the single most impactful technique in the system: it's what makes the panels read as physical glass objects rather than CSS rectangles.

---

## Rule 3 · The Grayscale Constraint

**Why no brand colors?**

Real glass has no pigment. It transmits and reflects. When you add a tinted background to a glass panel, it looks like a frosted piece of colored plastic: not glass.

The constraint forces a behavioral shift: the background video becomes the only source of color on the page. The glass panels become windows. Every hue the viewer perceives in the UI is actually the background showing through at different opacities. This is the constraint that makes the design feel premium rather than decorative.

**Why these specific opacity steps?**

The four text opacities (100 / 80 / 60 / 50) are spaced to create readable hierarchy with enough contrast at each level. Below 50%, text loses legibility on blurred backgrounds. The three background opacities (15 / 10 for fills, 30 for dividers) are chosen so they're visible but don't compete with text.

A rigid table prevents the "opacity drift" that happens when values are chosen freely: where 12 slightly different opacities create noise instead of hierarchy.

---

## Rule 4 · Typography

**Why Poppins + Source Serif 4?**

Poppins is a geometric sans that reads cleanly at small sizes in UI contexts (labels, descriptions, nav). Source Serif 4 italic has texture and weight that contrasts with Poppins without clashing: it reads as intentional rather than decorative.

**Why only 2–3 words of serif?**

The serif creates a visual anchor: the place the eye goes first when scanning the page. That effect depends entirely on scarcity. Three serif words on a page reads as editorial precision. Twenty serif words reads as a magazine template.

**Why `tracking-[-0.05em]` on H1?**

At 6xl–7xl, default letter spacing looks loose. The negative tracking tightens the heading into a single visual unit and makes large type look intentional rather than simply enlarged.

---

## Rule 5 · Layout Architecture

**Why glass-panel as a separate absolute div with `pointer-events-none`?**

If the glass effect is applied to the layout container itself, nesting and overflow interactions become complex to manage. Separating the glass overlay (absolute, pointer-events-none) from the content container (relative, normal flow) means:

- The glass renders correctly at `inset-4` without clipping content
- Content layout is unaffected by the backdrop-filter
- Adding `rounded-3xl` to the overlay doesn't affect the content's border-radius

**Why `inset-4` instead of `inset-0`?**

A small inset (16px) means the glass panel floats slightly away from the viewport edges. This creates visible separation between the panel and the edge, which helps the eye perceive it as an object in space rather than a flat background.

---

## Rule 6 · Micro-interactions

**Why `scale-105` and not a larger value like `scale-110`?**

At 1.05, the hover feels responsive: like the element is acknowledging your cursor. At 1.10, it starts to feel exaggerated and toy-like. The subtle scale is what reads as premium; obvious scale reads as novelty.

**Why `active:scale-95`?**

This is the tactile feedback. When you press a physical button, it moves *toward* you (compresses). `active:scale-95` replicates that compression feedback on release. Without it, clicks feel unconfirmed: the UI doesn't acknowledge that anything happened. Including it is the difference between "nice-looking UI" and "designed interaction."

**Why `transition-colors` on links instead of scale?**

Text links and icons that scale on hover create visual instability: the surrounding text reflows slightly. Color transitions communicate interactivity without disrupting layout.

---

## Making Adjustments

If you need to adapt the system for a different context:

**Changing blur values:** Keep the ratio: if you reduce the panel blur, reduce card and pill proportionally. The depth hierarchy depends on the gaps between tiers, not the absolute values.

**Adding a third font:** Don't. The power of the serif accent depends on contrast with Poppins. Adding a third typeface reduces both.

**Adding color to one panel:** Acceptable if the panel represents a different object (e.g., a notification or alert). Keep it subtle (`bg-blue-900/30`) and treat it as an exception, not a pattern.

**No video background:** The system works over static images. Replace `GlassSceneClient` with a `<Image>` component in a fixed-position container. The glass tiers and color constraint still apply.

**Mobile layout:** The right panel (`hidden lg:flex`) can be converted to a stacked section below the hero on mobile. Apply the same glass tiers: just use `glass-card` instead of the `glass-panel` outer container since mobile screens have less depth to spare.
