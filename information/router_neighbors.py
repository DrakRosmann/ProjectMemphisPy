class RouterNeighbors:
    """
    Calcula os vizinhos de um roteador a partir do seu endereço hamiltoniano.
    Os métodos retornam -1 quando o vizinho não existe (borda da malha).
    """

    def __init__(self, x_dimension, y_dimension):
        self.x_dimension = x_dimension
        self.y_dimension = y_dimension

    @classmethod
    def from_config(cls, mpsoc_config):
        return cls(mpsoc_config.mpsoc_x, mpsoc_config.mpsoc_y)

    def xy_to_ham_addr(self, xy_addr):
        xy_addr &= 0xFFFF  # limpa o header
        y = xy_addr & 0xFF
        x = xy_addr >> 8

        if y % 2 == 1:
            return (y * self.x_dimension) + (self.x_dimension - x) - 1
        return (y * self.x_dimension) + x

    def ham_to_xy_addr(self, ham_addr):
        ham_addr &= 0xFF  # limpa o header
        y, addr = divmod(ham_addr, self.x_dimension)

        x = self.x_dimension - addr - 1 if y % 2 == 1 else addr
        return (x << 8) | y

    def xy_address_to_xy_label(self, ham_addr):
        xy_addr = self.ham_to_xy_addr(ham_addr)
        return f"{xy_addr >> 8}{xy_addr & 0xFF}"

    def get_x_coordinate(self, ham_addr):
        return self.ham_to_xy_addr(ham_addr) >> 8

    def get_y_coordinate(self, ham_addr):
        return self.ham_to_xy_addr(ham_addr) & 0xFF

    def _neighbor(self, ham_addr, dx, dy):
        x = self.get_x_coordinate(ham_addr) + dx
        y = self.get_y_coordinate(ham_addr) + dy

        if 0 <= x < self.x_dimension and 0 <= y < self.y_dimension:
            return self.xy_to_ham_addr((x << 8) | y)
        return -1

    def get_vizinho_cima(self, ham_addr):
        return self._neighbor(ham_addr, 0, 1)

    def get_vizinho_baixo(self, ham_addr):
        return self._neighbor(ham_addr, 0, -1)

    def get_vizinho_esquerda(self, ham_addr):
        return self._neighbor(ham_addr, -1, 0)

    def get_vizinho_direita(self, ham_addr):
        return self._neighbor(ham_addr, 1, 0)
