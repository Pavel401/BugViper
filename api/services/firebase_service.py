"""BugViperFirebaseService - Firebase Admin SDK + Firestore user operations."""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel

from common.firebase_init import _initialize_firebase
from common.firebase_models import FirebaseUserData, FirebaseUserProfile


def _to_dict(data: BaseModel | dict[str, Any]) -> dict[str, Any]:
    """
    Convert a Pydantic BaseModel or dict into a Firestore-ready dictionary.
    
    If `data` is a Pydantic BaseModel, returns its serialized form using model aliases and excluding None values. If `data` is already a dict, returns it unchanged.
    
    Returns:
        dict: Dictionary suitable for writing to Firestore (keys use model aliases and None values are removed).
    """
    if isinstance(data, BaseModel):
        return data.model_dump(by_alias=True, exclude_none=True)
    return data

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
    ) -> FirebaseUserProfile:
        """
        Create or update the user's Firestore document using GitHub profile data and Firebase token claims.
        
        Parameters:
            uid (str): Firebase user ID.
            github_access_token (str): GitHub OAuth token to store for later API use.
            github_profile (dict): Response from GitHub's /user API; may be empty on failure.
            firebase_claims (dict): Decoded Firebase ID token claims used as fallback values.
        
        Returns:
            FirebaseUserProfile: Public user profile containing uid, email, display_name, github_username, photo_url, and created_at (does not include the GitHub access token).
        """
        now = datetime.now(timezone.utc).isoformat()

        email = github_profile.get("email") or firebase_claims.get("email")
        display_name = github_profile.get("name") or firebase_claims.get("name")
        github_username = github_profile.get("login")
        photo_url = github_profile.get("avatar_url") or firebase_claims.get("picture")

        doc_ref = self._db.collection("users").document(uid)
        doc = doc_ref.get()

        user_doc = FirebaseUserData(
            uid=uid,
            email=email,
            display_name=display_name,
            github_username=github_username,
            github_access_token=github_access_token,
            photo_url=photo_url,
            last_login=now,
        )

        if doc.exists:
            doc_ref.update(_to_dict(user_doc))
            created_at = doc.to_dict().get("createdAt")
        else:
            full_doc = {**_to_dict(user_doc), "createdAt": now}
            doc_ref.set(full_doc)
            created_at = now

        return FirebaseUserProfile(
            uid=uid,
            email=email,
            display_name=display_name,
            github_username=github_username,
            photo_url=photo_url,
            created_at=created_at,
        )

    def ensure_user(self, uid: str, firebase_claims: dict) -> FirebaseUserProfile:
        """
        Ensure a Firestore user document exists for the given uid, creating a minimal record from Firebase token claims if absent.
        
        If a user document already exists, updates its lastLogin timestamp. If no document exists, creates one using fields from firebase_claims (email, name, picture) and sets createdAt and lastLogin to the current time.
        
        Parameters:
            uid (str): The Firebase user ID.
            firebase_claims (dict): Authentication token claims from Firebase (may include keys like "email", "name", "picture").
        
        Returns:
            FirebaseUserProfile: The public-facing profile for the existing or newly created user.
        """
        now = datetime.now(timezone.utc).isoformat()
        doc_ref = self._db.collection("users").document(uid)
        doc = doc_ref.get()

        if doc.exists:
            doc_ref.update({"lastLogin": now})
            data = doc.to_dict()
            return FirebaseUserProfile(
                uid=uid,
                email=data.get("email"),
                display_name=data.get("displayName"),
                github_username=data.get("githubUsername"),
                photo_url=data.get("photoURL"),
                created_at=data.get("createdAt"),
            )

        # First time — create from Firebase token claims
        new_user = FirebaseUserData(
            uid=uid,
            email=firebase_claims.get("email"),
            display_name=firebase_claims.get("name"),
            photo_url=firebase_claims.get("picture"),
            created_at=now,
            last_login=now,
        )
        doc_ref.set(_to_dict(new_user))

        return FirebaseUserProfile(
            uid=uid,
            email=new_user.email,
            display_name=new_user.display_name,
            photo_url=new_user.photo_url,
            created_at=now,
        )

    def get_user(self, uid: str) -> Optional[FirebaseUserProfile]:
        """
        Retrieve a user's Firebase profile by UID.
        
        Returns:
            FirebaseUserProfile | None: The user's profile when a document exists for `uid`, otherwise `None`.
        """
        doc = self._db.collection("users").document(uid).get()
        if not doc.exists:
            return None

        data = doc.to_dict()
        return FirebaseUserProfile(
            uid=uid,
            email=data.get("email"),
            display_name=data.get("displayName"),
            github_username=data.get("githubUsername"),
            photo_url=data.get("photoURL"),
            created_at=data.get("createdAt"),
        )

    def get_github_token(self, uid: str) -> Optional[str]:
        """
        Retrieve the stored GitHub access token for a user.
        
        Returns:
            The GitHub access token if present, or `None` if the user document is missing or has no token.
        """
        doc = self._db.collection("users").document(uid).get()
        if not doc.exists:
            return None
        return doc.to_dict().get("githubAccessToken")


    # ── Repo metadata ─────────────────────────────────────────────────────

    def upsert_repo_metadata(
        self,
        uid: str,
        owner: str,
        repo: str,
        data: BaseModel | dict[str, Any],
    ) -> None:
        """
        Create or update repository metadata for a user in Firestore.
        
        The document is stored at users/{uid}/repos/{owner}_{repo}. The provided `data` (a Pydantic BaseModel or a plain dict) is serialized and merged into the document; `updatedAt` is always set to the current UTC timestamp and `createdAt` is set when the document is first created.
        
        Parameters:
            data (BaseModel | dict[str, Any]): Repo metadata payload to upsert; may be a Pydantic model or a dict. The payload will be converted to a Firestore-ready dict and merged into the repository document.
        """
        repo_key = f"{owner}_{repo}"
        now = datetime.now(timezone.utc).isoformat()
        doc_ref = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .document(repo_key)
        )
        doc = doc_ref.get()
        payload = {**_to_dict(data), "updatedAt": now}
        if doc.exists:
            doc_ref.update(payload)
        else:
            payload["createdAt"] = now
            doc_ref.set(payload)
        logger.info(f"Upserted repo metadata for {owner}/{repo} (uid={uid})")

    def get_repo_metadata(self, uid: str, owner: str, repo: str) -> Optional[dict]:
        """
        Retrieve repository metadata for a user.
        
        Returns:
            dict | None: `None` if the repo metadata document does not exist, otherwise the document data as a dict.
        """
        repo_key = f"{owner}_{repo}"
        doc = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .document(repo_key)
            .get()
        )
        return doc.to_dict() if doc.exists else None

    def delete_repo_metadata(self, uid: str, owner: str, repo: str) -> None:
        """
        Delete a repository metadata document and all nested PR and review documents for a user.
        
        Removes the document at users/{uid}/repos/{owner}_{repo} by deleting each document in its `prs` subcollection and each document in each PR's `reviews` subcollection.
        
        Parameters:
            uid (str): User UID owning the repository.
            owner (str): Repository owner/login.
            repo (str): Repository name.
        """
        repo_key = f"{owner}_{repo}"
        repo_ref = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .document(repo_key)
        )
        # Delete prs subcollection and their reviews
        for pr_doc in repo_ref.collection("prs").stream():
            for review_doc in pr_doc.reference.collection("reviews").stream():
                review_doc.reference.delete()
            pr_doc.reference.delete()
        repo_ref.delete()
        logger.info(f"Deleted repo metadata for {owner}/{repo} (uid={uid})")

    def list_repos(self, uid: str) -> list[dict]:
        """
        List all repository metadata documents ingested for the given user.
        
        Parameters:
            uid (str): Firebase user ID whose repo documents will be listed.
        
        Returns:
            list[dict]: A list of repository metadata dictionaries, one per repo document.
        """
        docs = (
            self._db.collection("users")
            .document(uid)
            .collection("repos")
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    # ── User lookup by GitHub username ────────────────────────────────────

    def lookup_uid_by_github_username(self, github_username: str) -> Optional[str]:
        """
        Finds the Firebase UID for a given GitHub username.
        
        Returns:
            The UID of the matching user as a string, or `None` if no user with that GitHub username exists.
        """
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

    def upsert_pr_metadata(
        self,
        uid: str,
        owner: str,
        repo: str,
        pr_number: int,
        pr_data: BaseModel | dict[str, Any],
    ) -> None:
        """
        Create or update pull request metadata for the specified user, repository, and PR number.
        
        If a document exists it is updated with the provided data and `updatedAt` timestamp.
        If no document exists it is created with `createdAt`, `updatedAt`, and initial
        `reviewCount` and `openIssueCount` set to 0. `pr_data` may be a Pydantic BaseModel
        or a plain dict and will be serialized before storage.
        
        Parameters:
            pr_data (BaseModel | dict[str, Any]): PR metadata payload to store.
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
        payload = {**_to_dict(pr_data), "updatedAt": now}
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
        run_data: BaseModel | dict[str, Any],
    ) -> str:
        """
        Save a review run for the given pull request and update the PR's review tallies.
        
        The run is assigned a sequential run number (e.g., run_1, run_2) based on existing reviews; the PR document's reviewCount, openIssueCount, and lastReviewedAt fields are updated when the PR exists.
        
        Parameters:
            run_data (BaseModel | dict[str, Any]): A ReviewRunData model or a plain dict representing the run; will be serialized for storage.
        
        Returns:
            str: The created run document ID (for example, "run_2").
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

        run_dict = _to_dict(run_data)
        run_ref = pr_ref.collection("reviews").document(run_id)
        run_ref.set({**run_dict, "runNumber": run_number, "createdAt": now})

        # Update PR-level tallies
        open_count = len([i for i in run_dict.get("issues", []) if i.get("status") != "fixed"])
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