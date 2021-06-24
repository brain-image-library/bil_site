BEGIN;
--
-- Add field name to project
--
ALTER TABLE "ingest_project" ALTER COLUMN "name" SET DEFAULT 'Project Name';
ALTER TABLE "ingest_project" ALTER COLUMN "name" SET NOT NULL;
--ALTER TABLE "ingest_project" ALTER COLUMN "name" DROP DEFAULT;
--
-- Create model DataGroup
--
CREATE TABLE "ingest_datagroup" ("id" serial NOT NULL PRIMARY KEY, "data_group_list_id" integer NOT NULL, "dm_id_id" integer NOT NULL);
ALTER TABLE "ingest_datagroup" ADD CONSTRAINT "ingest_datagroup_dm_id_id_ce6b3e7d_fk_ingest_de" FOREIGN KEY ("dm_id_id") REFERENCES "ingest_descriptivemetadata" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_datagroup_dm_id_id_ce6b3e7d" ON "ingest_datagroup" ("dm_id_id");
select * from ingest_datagroup;
select * from ingest_project;
ROLLBACK;
