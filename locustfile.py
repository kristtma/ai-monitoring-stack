import random
from locust import HttpUser, TaskSet, between, task


class BackendTasks(TaskSet):

    @task(5)
    def get_users(self):
        self.client.get("/api/users", name="GET /api/users")

    @task(3)
    def health_check(self):
        self.client.get("/health", name="GET /health")

    @task(2)
    def matrix_compute(self):
        size = random.randint(20, 60)
        self.client.post(
            "/compute/matrix",
            data={"size": size},
            name="POST /compute/matrix",
        )

    @task(2)
    def hash_string(self):
        self.client.post(
            "/security/hash",
            data={"string": "monitoring-test-payload", "size": random.randint(100, 500)},
            name="POST /security/hash",
        )

    @task(1)
    def generate_report(self):
        self.client.post(
            "/reports/list",
            data={"size": random.randint(1000, 5000)},
            name="POST /reports/list",
        )


class FrontendTasks(TaskSet):

    @task
    def visit_homepage(self):
        self.client.get("/", name="GET / (frontend)")


class BackendUser(HttpUser):
    tasks = [BackendTasks]
    wait_time = between(0.1, 0.5)


class HeavyUser(HttpUser):
    tasks = {BackendTasks: 1}
    wait_time = between(0.5, 1.5)

    @task(10)
    def hammer_matrix(self):
        size = random.randint(80, 150)
        self.client.post(
            "/compute/matrix",
            data={"size": size},
            name="POST /compute/matrix [heavy]",
        )
