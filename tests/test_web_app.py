"""Integration tests for SigapStok Web Application core user flow."""

import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

from web_app import AppState, make_handler


class TestWebApp(unittest.TestCase):
    def test_web_core_user_flow_demo_adjust_budget_and_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = AppState(db_path=Path(tmp) / "web_test.db")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            port = server.server_address[1]
            t = threading.Thread(target=server.serve_forever, daemon=True)
            t.start()
            try:
                base = f"http://127.0.0.1:{port}"
                # 1. Load synthetic demo
                req = Request(f"{base}/api/demo?budget=35000000", method="POST")
                with urlopen(req) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                self.assertGreater(len(data["rows"]), 10)
                first_id = data["rows"][0]["drug_id"]

                # 2. Manual adjustment with reason
                adj_body = json.dumps({"drug_id": first_id, "new_qty": 12, "reason": "Ward surge"}).encode("utf-8")
                adj_req = Request(f"{base}/api/adjust", data=adj_body, headers={"Content-Type": "application/json"}, method="POST")
                with urlopen(adj_req) as resp:
                    adj_data = json.loads(resp.read().decode("utf-8"))
                matched = [r for r in adj_data["rows"] if r["drug_id"] == first_id][0]
                self.assertEqual(matched["requested_qty"], 12.0)
                self.assertTrue(matched["manual_adjusted"])

                # 3. Export CSV
                with urlopen(f"{base}/api/export_csv") as resp:
                    csv_text = resp.read().decode("utf-8")
                self.assertIn("Expected Days Without Stock", csv_text)
            finally:
                server.shutdown()
                server.server_close()
                state.db.close()


if __name__ == "__main__":
    unittest.main()
