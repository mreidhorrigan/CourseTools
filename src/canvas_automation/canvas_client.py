"""
Thin wrapper around the parts of the Canvas LMS REST API this project uses.

Nothing in this file knows about Flask, jsonc, or HTTP routing. It is plain
Python so the same functions can be reused directly by something else later,
such as an MCP server, without touching this logic.

Canvas API reference: https://developerdocs.instructure.com/services/canvas
"""
import requests
import mimetypes


class CanvasClient:
    """A small, session-based client for the Canvas REST API (v1)."""

    def __init__(self, base_url, token, timeout=30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        })

    def _url(self, path):
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = "/" + path
        if not path.startswith("/api/"):
            path = "/api/v1" + path
        return self.base_url + path

    def whoami(self):
        """Used at startup to confirm the token and base_url actually work."""
        resp = self.session.get(self._url("/users/self"), timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get(self, path, params=None):
        return self.session.get(self._url(path), params=params, timeout=self.timeout)

    def post(self, path, json_body=None):
        return self.session.post(self._url(path), json=json_body, timeout=self.timeout)

    def put(self, path, json_body=None):
        return self.session.put(self._url(path), json=json_body, timeout=self.timeout)

    def patch(self, path, json_body=None):
        return self.session.patch(self._url(path), json=json_body, timeout=self.timeout)

    def delete(self, path):
        return self.session.delete(self._url(path), timeout=self.timeout)

    def upload_course_file(self, course_id, filename, content, parent_folder_path="quiz-images"):
        content_type=mimetypes.guess_type(filename)[0] or "application/octet-stream"
        init=self.session.post(self._url(f"/courses/{course_id}/files"),json={"name":filename,"size":len(content),
            "content_type":content_type,"parent_folder_path":parent_folder_path,"on_duplicate":"overwrite"},timeout=self.timeout)
        init.raise_for_status(); ticket=init.json()
        upload=requests.post(ticket["upload_url"],data=ticket.get("upload_params",{}),
                             files={"file":(filename,content,content_type)},allow_redirects=False,timeout=self.timeout)
        upload.raise_for_status(); location=upload.headers.get("Location")
        if location:
            done=self.session.get(location,timeout=self.timeout); done.raise_for_status(); return done
        return upload

    def upload_content_migration(self, course_id, filename, content):
        """Create and upload a Common Cartridge content migration."""
        content_type = "application/zip"
        init = self.session.post(
            self._url(f"/courses/{course_id}/content_migrations"),
            json={
                # This package carries Canvas course_settings, quiz metadata,
                # and rubrics in addition to Common Cartridge resources.
                "migration_type": "canvas_cartridge_importer",
                "pre_attachment": {
                    "name": filename,
                    "size": len(content),
                    "content_type": content_type,
                },
            },
            timeout=self.timeout,
        )
        init.raise_for_status()
        migration = init.json()
        ticket = migration.get("pre_attachment") or {}
        upload_url = ticket.get("upload_url")
        if not upload_url:
            raise RuntimeError(f"Canvas migration did not return an upload URL: {migration}")
        upload = requests.post(
            upload_url,
            data=ticket.get("upload_params", {}),
            files={"file": (filename, content, content_type)},
            allow_redirects=False,
            timeout=120,
        )
        upload.raise_for_status()
        return {
            "migration": migration,
            "upload_status": upload.status_code,
            "upload_location": upload.headers.get("Location"),
        }

    def get_all_pages(self, path, params=None):
        """
        GET a Canvas list endpoint, following the Link: rel="next" header
        until it is exhausted, and return every item as one combined list.
        If the endpoint returns a single object instead of a list, that
        object is returned as is.
        """
        results = []
        url = self._url(path)
        next_params = params
        while url:
            resp = self.session.get(url, params=next_params, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            if not isinstance(data, list):
                return data
            results.extend(data)
            url = resp.links.get("next", {}).get("url")
            next_params = None
        return results


def build_rubric_criteria_hash(criteria):
    """
    Convert a plain list of rubric criteria into the indexed-Hash shape
    Canvas's Rubrics API requires for `rubric[criteria]`.

    Canvas's own docs describe this parameter as an indexed Hash of
    RubricCriteria objects where the keys are integer ids. In
    form-encoding terms that is:
        rubric[criteria][0][description]=...
        rubric[criteria][0][ratings][0][description]=...
    As JSON, the equivalent is nested objects keyed "0", "1", "2", not a
    JSON array. Sending an array here is the single most common way this
    endpoint silently misbehaves, so the conversion lives in one
    well-commented place instead of being left to whoever writes a config.
    See research/canvas-api-endpoints.md for how this was confirmed.
    """
    criteria_hash = {}
    for i, crit in enumerate(criteria):
        entry = {
            "description": crit.get("description", ""),
            "points": crit.get("points", 0),
        }
        if "long_description" in crit:
            entry["long_description"] = crit["long_description"]
        if "criterion_use_range" in crit:
            entry["criterion_use_range"] = crit["criterion_use_range"]

        ratings = crit.get("ratings") or []
        if ratings:
            ratings_hash = {}
            for j, rating in enumerate(ratings):
                rating_entry = {
                    "description": rating.get("description", ""),
                    "points": rating.get("points", 0),
                }
                if "long_description" in rating:
                    rating_entry["long_description"] = rating["long_description"]
                ratings_hash[str(j)] = rating_entry
            entry["ratings"] = ratings_hash

        criteria_hash[str(i)] = entry
    return criteria_hash
