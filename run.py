from app.core.MastControl import MastControl

if __name__ == '__main__':
    md_path = r'D:\pythonproject\Ai_Blogger\Md'
    playwright_driver_data = r'D:\pythonproject\Ai_Blogger\driver\playwright_data'
    mast_control = MastControl(md_path=md_path, playwright_driver_data=playwright_driver_data)

    mast_control.run()
