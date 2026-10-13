"""Optional baseline comparison; never create/update a baseline to hide a failure."""
from pathlib import Path
import math
from .artifacts import file_digest
from .suite import Unsupported


def compare_png(current: Path, baseline: Path, *, current_context: dict,
                baseline_context: dict, max_changed_ratio: float, channel_tolerance=0, masks=()):
    try:
        from PIL import Image, ImageChops, ImageDraw
    except ImportError as exc:
        raise Unsupported('use the existing visual matcher; Pillow is not installed') from exc
    if not current_context or current_context != baseline_context:
        return {'status': 'INCONCLUSIVE', 'classification': 'BASELINE_ENVIRONMENT_MISMATCH'}
    if not math.isfinite(max_changed_ratio) or not 0 <= max_changed_ratio <= 1 or not 0 <= channel_tolerance <= 255:
        raise ValueError('invalid approved visual threshold')
    if not baseline.is_file():
        return {'status': 'NOT_RUN', 'classification': 'APPROVED_BASELINE_MISSING'}
    with Image.open(current) as a, Image.open(baseline) as b:
        if a.size != b.size:
            return {'status': 'FAIL', 'evidence': 'Baseline and current image dimensions differ'}
        left, right = a.convert('RGB'), b.convert('RGB')
    compared = Image.new("1", left.size, 1)
    for mask in masks:
        if len(mask) != 4 or mask[0] < 0 or mask[1] < 0 or mask[2] > left.width or mask[3] > left.height:
            raise ValueError('mask is outside the approved image region')
        if mask[0] >= mask[2] or mask[1] >= mask[3]:
            raise ValueError('mask must have positive dimensions')
        ImageDraw.Draw(compared).rectangle((mask[0],mask[1],mask[2]-1,mask[3]-1), fill=0)
    difference = ImageChops.difference(left, right)
    pixels = lambda image: image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata()
    flags = list(pixels(compared))
    denominator = sum(flags)
    if not denominator: raise ValueError('mask cannot remove the entire comparison')
    changed = sum(bool(flag) and max(pixel) > channel_tolerance for flag,pixel in zip(flags,pixels(difference)))
    ratio = changed / denominator
    return {'status': 'PASS' if ratio <= max_changed_ratio else 'FAIL',
            'evidence': 'Approved rendered baseline compared under the declared rendering context',
            'changed_ratio': ratio, 'threshold': max_changed_ratio,
            'current_sha256': file_digest(current), 'baseline_sha256': file_digest(baseline),
            'scope': 'visual regression; not design approval or functional correctness'}
