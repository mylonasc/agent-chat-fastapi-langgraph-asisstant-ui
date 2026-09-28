from agent_chat_minimal.adapters import InMemoryRepositories

from repository_contract import RepositoryContract


class TestInMemoryRepositories(RepositoryContract):
    def make_repositories(self):
        return InMemoryRepositories()
