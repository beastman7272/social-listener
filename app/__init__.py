import os

from flask import Flask


def create_app():
    app = Flask(
    __name__,
    template_folder="../templates",
    static_folder="../static",
    instance_relative_config=True,
)

    app.config.from_mapping(
        DATABASE=os.path.join(app.instance_path, "social_listener.db"),
    )

    os.makedirs(app.instance_path, exist_ok=True)

    from .routes import bp as routes_bp

    app.register_blueprint(routes_bp)

    return app
