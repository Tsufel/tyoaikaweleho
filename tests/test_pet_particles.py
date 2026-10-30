"""The generated pet particle boxes stay in step with the sprite art."""
import importlib.util
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("pet_particles", os.path.join(ROOT, "scripts", "pet_particles.py"))
pet_particles = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pet_particles)


def test_generated_file_is_current():
    with open(pet_particles.OUT, encoding="utf-8") as f:
        on_disk = f.read()
    assert on_disk == pet_particles.render(), "re-run: python scripts/pet_particles.py"


def test_every_sleepy_pose_has_zs():
    text = pet_particles.render()
    for kind in ("familiar", "wizard"):
        for pose in ("drowsy", "sleep"):
            block = text.split(f"  {kind}_{pose}: [")[1].split("],")[0]
            assert "kind: 'z'" in block, f"{kind}_{pose} lost its z's"
