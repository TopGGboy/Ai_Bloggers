from app.core.MastControl import MastControl

if __name__ == '__main__':
    edge_driver_path = r'driver/edgedriver/msedgedriver.exe'
    md_path = r'Md'
    mast_control = MastControl(edge_driver_path=edge_driver_path, md_path=md_path)

    mast_control.run()
