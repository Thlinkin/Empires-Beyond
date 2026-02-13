import os, unittest, json
from main import Runtime, ZoteError, state_hash

ROOT = os.path.dirname(os.path.abspath(__file__))

class TestZoteScript(unittest.TestCase):
    def setUp(self):
        self.rt = Runtime(root_dir=ROOT, debug=False)

    def load(self, path):
        return self.rt.load_module(path)

    def call(self, env, name, *args):
        fnv = env[name]
        return self.rt._call(fnv, list(args), None if False else type("T",(),{"line":1,"col":1})(), path := "test")

    def test_rng_determinism(self):
        env = self.load("rules/main.zs")
        self.rt._call(env["rng_seed"], [123], None, "t")
        a = self.rt._call(env["rng_int"], [1,6], None, "t")
        self.rt._call(env["rng_seed"], [123], None, "t")
        b = self.rt._call(env["rng_int"], [1,6], None, "t")
        self.assertEqual(a,b)

    def test_parse_runtime_basic(self):
        env = self.load("rules/main.zs")
        self.assertIn("init_game", env)
        st = self.rt._call(env["init_game"], [42], None, "t")
        self.assertIsInstance(st, dict)

    def test_replay_hash(self):
        env = self.load("rules/main.zs")
        self.rt._call(env["rng_seed"], [999], None, "t")
        st = self.rt._call(env["init_game"], [999], None, "t")
        # do one tick with no actions
        out = self.rt._call(env["tick"], [st], None, "t")
        st2 = out["state"]
        h1 = state_hash(self.rt._call(env["serialize"], [st2], None, "t"))
        # replay again
        self.rt = Runtime(root_dir=ROOT, debug=False)
        env = self.rt.load_module("rules/main.zs")
        self.rt._call(env["rng_seed"], [999], None, "t")
        st = self.rt._call(env["init_game"], [999], None, "t")
        out = self.rt._call(env["tick"], [st], None, "t")
        st2 = out["state"]
        h2 = state_hash(self.rt._call(env["serialize"], [st2], None, "t"))
        self.assertEqual(h1,h2)

if __name__ == "__main__":
    unittest.main()
