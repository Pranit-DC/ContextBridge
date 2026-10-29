"""Context-only judge with a freshness fence after quota waiting."""

from contextbridge.formation.providers.interpretation import ChatSearchEvidenceJudge


class ContextEvidenceJudge:
    def __init__(self, client):
        self.client = client
        self.delegate = ChatSearchEvidenceJudge(client)

    def bind_guard(self, guard):
        previous = self.client.before_call
        self.client.before_call = guard
        return previous

    def judge(self, claim, evidence):
        return self.delegate.judge(claim, evidence)
