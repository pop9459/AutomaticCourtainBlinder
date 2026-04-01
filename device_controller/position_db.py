try:
    import ujson as json
except ImportError:
    import json


class PositionDB:
    def __init__(self, filename="positions.json"):
        self.filename = filename

    def load_json_file(self, filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_json_file(self, filename, data):
        with open(filename, "w") as f:
            json.dump(data, f)

    def load_positions(self):
        data = self.load_json_file(self.filename)
        if not isinstance(data, dict):
            data = {}

        return {
            "current_position": data.get("current_position", 0),
            "position_open": data.get("position_open", None),
            "position_closed": data.get("position_closed", None),
        }

    def save_positions(self, current_position, position_open, position_closed):
        self.save_json_file(
            self.filename,
            {
                "current_position": current_position,
                "position_open": position_open,
                "position_closed": position_closed,
            },
        )

    def reset_positions(self):
        self.save_positions(0, None, None)
