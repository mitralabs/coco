## Database Migrations

The DB API service uses Alembic for database migrations. All database models are defined in `app/models.py` and migrations are managed through Docker. Follow these steps to modify the database schema:

### Making Changes to Database Models

1. **Modify the models.py file**:
   Edit `app/models.py` to add, remove, or modify database columns or tables.

   Example:

   ```python
   # Adding a new column to the Document model
   class Document(Base):
       # ... existing columns ...
       new_column = Column(String, nullable=True)
   ```

2. **Generate a migration script**:
   Run the following command to auto-generate a migration script:

   ```bash
   docker compose run --rm db-api alembic revision --autogenerate -m "description of your change"
   ```

   This will create a new file in `app/migrations/versions/` with upgrade and downgrade functions.

   Note that Alembic generates the migration script from the difference between the (new) database schema defined in `models.py` and the current state of the actual database. So make sure the database is in appropriate state (all previous migrations applied).

3. **Apply the migration**:
   Run the following command to apply the migration:

   ```bash
   docker compose run --rm db-api alembic upgrade head
   ```

   This will update the database schema to the latest version.

4. **Verify the changes**:
   You can check the current database state with:
   ```bash
   docker compose run --rm db-api alembic current
   ```

### Common Alembic Commands

- **View migration history**:

  ```bash
  docker compose run --rm db-api alembic history
  ```

- **Downgrade to a specific version**:

  ```bash
  docker compose run --rm db-api alembic downgrade <revision_id>
  ```

- **Downgrade one version**:
  ```bash
  docker compose run --rm db-api alembic downgrade -1
  ```
