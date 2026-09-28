from agent_chat_minimal.adapters import InMemoryRepositories

from repository_contract import RepositoryContract


class TestInMemoryRepositories(RepositoryContract):
    async def make_repositories(self):
        return InMemoryRepositories()
