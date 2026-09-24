from dataclasses import dataclass


@dataclass
class TaskInformation:
    """Um evento de tarefa (alocação, término, mensagem) ocorrido em um PE."""

    id: int
    service: str
    time: int
    remote_task_id: int = -1

    @property
    def task_id(self):
        # Os 8 bits menos significativos identificam a tarefa dentro da aplicação
        return self.id & 0xFF

    @property
    def app_id(self):
        return self.id >> 8
