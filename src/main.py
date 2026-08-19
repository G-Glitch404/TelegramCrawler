import os
import uvicorn


def main() -> None:
    """ start the api server """
    uvicorn.run(
        "src.api:app",
        host=os.environ.get("HOST", '0.0.0.0'),
        port=int(os.environ.get("PORT", 9097)),
        reload=False,
        access_log=False,
    )


if __name__ == "__main__":
    main()
