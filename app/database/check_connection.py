from sqlalchemy import text

from app.database.session import engine


async def check_database_connection():

    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT version()"))

            version = result.scalar_one()

            print("Database connection successful!")
            print(version)

    except Exception as error:
        print("Database connection failed!")
        print(error)

        raise

    finally:
        await engine.dispose()


if __name__ == "__main__":
    import asyncio
    import selectors

    asyncio.run(
        check_database_connection(),
        loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()),
    )
