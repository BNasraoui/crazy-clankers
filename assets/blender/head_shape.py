"""Shared anime head surface, in metres relative to the eye line.

HeadShape is the reusable construction for passengers. Width, height, depth,
jaw_width and nose can vary independently without changing the cylindrical UV
contract. Character hair and facial pigment remain separate art inputs.
"""

from dataclasses import dataclass
import math

# Height, half-width, front depth, rear depth. The lower rings sweep from a
# soft chin through the jaw to the cheek; the upper rings form an egg cranium.
SECTIONS = (
    (-0.108, 0.012, 0.067, 0.000),
    (-0.102, 0.027, 0.077, 0.006),
    (-0.086, 0.043, 0.080, 0.020),
    (-0.060, 0.056, 0.075, 0.038),
    (-0.038, 0.069, 0.073, 0.059),
    (-0.019, 0.077, 0.074, 0.076),
    (0, 0.079, 0.075, 0.087),
    (0.021, 0.078, 0.078, 0.093),
    (0.042, 0.077, 0.079, 0.095),
    (0.064, 0.072, 0.074, 0.092),
    (0.085, 0.063, 0.061, 0.081),
    (0.103, 0.044, 0.040, 0.057),
    (0.115, 0.016, 0.014, 0.023),
    (0.117, 0.002, 0.002, 0.003),
)


@dataclass(frozen=True)
class HeadShape:
    width: float = 1.0
    height: float = 1.0
    depth: float = 1.0
    jaw_width: float = 1.0
    nose: float = 1.0

    @property
    def sections(self):
        return tuple(
            (
                y * self.height,
                w * self.width * (1 + (self.jaw_width - 1) * max(0, min(1, -y / 0.06))),
                front * self.depth,
                rear * self.depth,
            )
            for y, w, front, rear in SECTIONS
        )

    def section(self, y):
        return interpolate_sections(self.sections, y)

    def surface(self, theta, y):
        rx, front, rear = self.section(y)
        s, c = math.sin(theta), math.cos(theta)
        x = rx * s
        z = front * c if c >= 0 else rear * c
        if c > 0:
            # Low ridge and rounded tip, integrated into the curved face.
            nx, ny = x / self.width, y / self.height
            z += (
                self.depth
                * self.nose
                * (
                    0.005 * math.exp(-((nx / 0.012) ** 2) - ((ny + 0.018) / 0.025) ** 2)
                    + 0.006
                    * math.exp(-((nx / 0.012) ** 2) - ((ny + 0.034) / 0.010) ** 2)
                )
            )
            z += (
                self.depth
                * 0.003
                * math.exp(-((nx / 0.030) ** 4) - ((ny + 0.061) / 0.016) ** 2)
            )
        return x, y, z


def interpolate_sections(sections, y):
    """Monotone cubic interpolation of any measured landmark columns."""
    i = next(
        (i for i in range(1, len(sections)) if sections[i][0] >= y), len(sections) - 1
    )
    a, b = sections[i - 1], sections[i]
    t = max(0, min(1, (y - a[0]) / (b[0] - a[0])))

    # Monotone cubic interpolation keeps silhouette tangents continuous and
    # cannot overshoot the chin or crown at closely spaced end sections.
    def slope(j, k):
        if j == 0:
            return (sections[1][k] - sections[0][k]) / (sections[1][0] - sections[0][0])
        if j == len(sections) - 1:
            return (sections[j][k] - sections[j - 1][k]) / (
                sections[j][0] - sections[j - 1][0]
            )
        left = (sections[j][k] - sections[j - 1][k]) / (
            sections[j][0] - sections[j - 1][0]
        )
        right = (sections[j + 1][k] - sections[j][k]) / (
            sections[j + 1][0] - sections[j][0]
        )
        return 0 if left * right <= 0 else 2 * left * right / (left + right)

    h = b[0] - a[0]
    return tuple(
        (2 * t**3 - 3 * t * t + 1) * a[k]
        + (t**3 - 2 * t * t + t) * h * slope(i - 1, k)
        + (-2 * t**3 + 3 * t * t) * b[k]
        + (t**3 - t * t) * h * slope(i, k)
        for k in range(1, len(sections[0]))
    )
