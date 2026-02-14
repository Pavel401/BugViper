"""BugViperFirebaseService - Firebase Admin SDK + Firestore user operations."""

import logging
from datetime import datetime, timezone
from typing import Optional

from common.firebase_init import _initialize_firebase

logger = logging.getLogger(__name__)


# ── Service Class ─────────────────────────────────────────────────────────────


class BugViperFirebaseService:
    """Singleton service for Firestore user operations."""

    _instance: Optional["BugViperFirebaseService"] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not BugViperFirebaseService._initialized:
            self._db = _initialize_firebase()
            BugViperFirebaseService._initialized = True

    @property
    def db(self):
        return self._db

    # ── User CRUD ─────────────────────────────────────────────────────────

    def create_or_update_user(
        self,
        uid: str,
        github_access_token: str,
        github_profile: dict,
        firebase_claims: dict,
    ) -> dict:
        """
        Create or update a user document in Firestore.

        Args:
            uid: Firebase user ID.
            github_access_token: GitHub OAuth token (stored for later API use).
            github_profile: Dict from GitHub /user API (may be empty on failure).
            firebase_claims: Decoded Firebase ID token claims (fallback values).

        Returns the user profile dict.
        """
        now = datetime.now(timezone.utc).isoformat()

        email = github_profile.get("email") or firebase_claims.get("email")
        display_name = github_profile.get("name") or firebase_claims.get("name")
        github_username = github_profile.get("login")
        photo_url = github_profile.get("avatar_url") or firebase_claims.get("picture")

        doc_ref = self._db.collection("users").document(uid)
        doc = doc_ref.get()

        user_data = {
            "uid": uid,
            "email": email,
            "displayName": display_name,
            "githubUsername": github_username,
            "githubAccessToken": github_access_token,
            "photoURL": photo_url,
            "lastLogin": now,
        }

        if doc.exists:
            doc_ref.update(user_data)
            created_at = doc.to_dict().get("createdAt")
        else:
            user_data["createdAt"] = now
            doc_ref.set(user_data)
            created_at = now

        return {
            "uid": uid,
            "email": email,
            "displayName": display_name,
            "githubUsername": github_username,
            "photoURL": photo_url,
            "createdAt": created_at,
        }

    def ensure_user(self, uid: str, firebase_claims: dict) -> dict:
        """
        Ensure user doc exists for returning sessions (no GitHub token needed).
        Creates a minimal doc from Firebase token claims if missing.

        Returns the user profile dict.
        """
        now = datetime.now(timezone.utc).isoformat()
        doc_ref = self._db.collection("users").document(uid)
        doc = doc_ref.get()

        if doc.exists:
            doc_ref.update({"lastLogin": now})
            data = doc.to_dict()
            return {
                "uid": uid,
                "email": data.get("email"),
                "displayName": data.get("displayName"),
                "githubUsername": data.get("githubUsername"),
                "photoURL": data.get("photoURL"),
                "createdAt": data.get("createdAt"),
            }

        # First time — create from Firebase token claims
        user_data = {
            "uid": uid,
            "email": firebase_claims.get("email"),
            "displayName": firebase_claims.get("name"),
            "photoURL": firebase_claims.get("picture"),
            "createdAt": now,
            "lastLogin": now,
        }
        doc_ref.set(user_data)

        return {
            "uid": uid,
            "email": user_data["email"],
            "displayName": user_data["displayName"],
            "photoURL": user_data["photoURL"],
            "createdAt": now,
        }

    def get_user(self, uid: str) -> Optional[dict]:
        """
        Fetch user profile from Firestore by UID.
        Returns None if user doc does not exist.
        """
        doc = self._db.collection("users").document(uid).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        return {
            "uid": uid,
            "email": data.get("email"),
            "displayName": data.get("displayName"),
            "githubUsername": data.get("githubUsername"),
            "photoURL": data.get("photoURL"),
            "createdAt": data.get("createdAt"),
        }

    def get_github_token(self, uid: str) -> Optional[str]:
        """
        Retrieve the stored GitHub access token for a user.
        Returns None if user doc doesn't exist or has no token.
        """
        doc = self._db.collection("users").document(uid).get()
        if not doc.exists:
            return None
        return doc.to_dict().get("githubAccessToken")


    # ── User lookup by GitHub username ────────────────────────────────────

    def lookup_uid_by_github_username(self, github_username: str) -> Optional[str]:
        """Return the Firebase UID for a given GitHub username, or None if not found."""
        docs = (
            self._db.collection("users")
            .where("githubUsername", "==", github_username)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.id
        return None

    # ── PR metadata ────────────────────────────────────────────────────────

    def upsert_pr_metadata(self, uid: str, owner: str, repo: str, pr_number: int, pr_data: dict) -> None:
        """
        Create or update the PR metadata document.

        Path: users/{uid}/repos/{owner}_{repo}/prs/{pr_number}
        """
        repo_key = f"{owner}_{repo}"
        now = datetime.now(timezone.utc).isoformat()
        doc_ref = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .document(repo_key)
            .collection("prs")
            .document(str(pr_number))
        )
        doc = doc_ref.get()
        payload = {**pr_data, "updatedAt": now}
        if doc.exists:
            doc_ref.update(payload)
        else:
            payload["createdAt"] = now
            payload["reviewCount"] = 0
            payload["openIssueCount"] = 0
            doc_ref.set(payload)

    # ── Review runs ────────────────────────────────────────────────────────

    def save_review_run(
        self,
        uid: str,
        owner: str,
        repo: str,
        pr_number: int,
        run_data: dict,
    ) -> str:
        """
        Save a review run document and update the PR's tallies.

        Path: users/{uid}/repos/{owner}_{repo}/prs/{pr_number}/reviews/run_{n}

        Returns the run document ID (e.g. "run_2").
        """
        repo_key = f"{owner}_{repo}"
        now = datetime.now(timezone.utc).isoformat()

        pr_ref = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .document(repo_key)
            .collection("prs")
            .document(str(pr_number))
        )

        # Determine next run number
        existing = list(pr_ref.collection("reviews").stream())
        run_number = len(existing) + 1
        run_id = f"run_{run_number}"

        run_ref = pr_ref.collection("reviews").document(run_id)
        run_ref.set({**run_data, "runNumber": run_number, "createdAt": now})

        # Update PR-level tallies
        open_count = len([i for i in run_data.get("issues", []) if i.get("status") != "fixed"])
        pr_doc = pr_ref.get()
        if pr_doc.exists:
            pr_ref.update({
                "reviewCount": run_number,
                "openIssueCount": open_count,
                "lastReviewedAt": now,
            })

        logger.info(f"Saved review run {run_id} for {owner}/{repo}#{pr_number}")
        return run_id

    def get_latest_review_run(
        self, uid: str, owner: str, repo: str, pr_number: int
    ) -> Optional[dict]:
        """
        Fetch the most recent review run document.
        Returns None if no previous run exists.
        """
        repo_key = f"{owner}_{repo}"
        runs_ref = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .document(repo_key)
            .collection("prs")
            .document(str(pr_number))
            .collection("reviews")
        )
        docs = list(runs_ref.order_by("runNumber", direction="DESCENDING").limit(1).stream())
        if not docs:
            return None
        return docs[0].to_dict()


# Module-level convenience instance (triggers Firebase init on import)
firebase_service = BugViperFirebaseService()
