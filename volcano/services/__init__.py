"""Domain services (use cases). Each one receives a SQLAlchemy session and is shared by the services
that need it; only `forecasting` and `training` pull in the ML stack, and only the engine imports them."""
