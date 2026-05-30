" python -m app.core.MultiPlatformManager"
" playwright codegen -o my_test.py https://passport.weibo.com/sso/signin "
import asyncio
from app.cli.repl import main

if __name__ == '__main__':
    asyncio.run(main())
