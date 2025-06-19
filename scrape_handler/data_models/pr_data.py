from dataclasses import dataclass, field


@dataclass
class PullRequestData:
    """Holds all data about a PR and creates a corresponding ID and tag."""
    number: str
    title: str
    description: str
    url: str
    diff_url: str
    base_branch: str
    base_commit: str
    head_branch: str
    head_commit: str
    owner: str
    repo: str
    id: str = field(init=False)
    image_tag: str = field(init=False)

    def __post_init__(self):
        # ensure description is never None
        if self.description is None:
            self.description = ""
        self.id = f"{self.owner}__{self.repo}-{self.number}"
        self.image_tag    = f"image_{self.id}"

    @classmethod
    def from_payload(cls, payload: dict) -> "PullRequestData":
        pr   = payload["pull_request"]
        repo = payload["repository"]
        return cls(
            number      = pr["number"],
            title       = pr["title"],
            description = pr["body"],
            url         = pr["url"],
            diff_url    = pr["diff_url"],
            base_branch = pr["base"]["ref"],
            base_commit = pr["base"]["sha"],
            head_branch = pr["head"]["ref"],
            head_commit = pr["head"]["sha"],
            owner       = repo["owner"]["login"],
            repo        = repo["name"],
        )
