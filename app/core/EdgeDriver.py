from selenium.webdriver import Edge
from selenium.webdriver.edge.service import Service
from selenium.webdriver.edge.options import Options


class EdgeDriver:
    def __init__(self, edge_driver_path=None):
        self.Edge_op = Options()
        self.Edge_op.add_experimental_option("debuggerAddress", "127.0.0.1:9222")

        if edge_driver_path is None:
            edge_driver_path = r'../../driver/edgedriver/msedgedriver.exe'
            # edge_driver_path = '../../../driver/edgedriver/msedgedriver.exe'

        self.ser = Service(executable_path=edge_driver_path)

    # 启动新的Edge
    def new_Edge(self):
        driver = Edge(service=self.ser)
        return driver

    # 控制已经存在的Edge
    def control_Edge(self):
        driver = Edge(options=self.Edge_op, service=self.ser)
        return driver


if __name__ == '__main__':
    pass
