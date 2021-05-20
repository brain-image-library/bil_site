BEGIN;
--
-- Create model Collection
--
--
-- Create model Funder
--
CREATE TABLE "ingest_funder" ("id" serial NOT NULL PRIMARY KEY, "name" varchar(256) NOT NULL, "funding_reference_identifier" varchar(256) NOT NULL, "funding_reference_identifier_type" varchar(256) NOT NULL, "award_number" varchar(256) NOT NULL, "award_title" varchar(256) NOT NULL, "grant_number" varchar(256) NOT NULL);
--
-- Create model People
--
CREATE TABLE "ingest_people" ("id" serial NOT NULL PRIMARY KEY, "name" varchar(256) NOT NULL, "orcid" varchar(256) NOT NULL, "affiliation" varchar(256) NOT NULL, "affiliation_identifier" varchar(256) NOT NULL, "auth_user_id_id" integer NULL);
--
-- Create model Project
--
CREATE TABLE "ingest_project" ("id" serial NOT NULL PRIMARY KEY, "funded_by" varchar(256) NOT NULL, "is_biccn" boolean NOT NULL);
--
-- Create model UUID
--
CREATE TABLE "ingest_uuid" ("id" serial NOT NULL PRIMARY KEY, "useduuid" varchar(256) NOT NULL UNIQUE);
--
-- Create model ProjectPeople
--
CREATE TABLE "ingest_projectpeople" ("id" serial NOT NULL PRIMARY KEY, "is_pi" boolean NOT NULL, "is_po" boolean NOT NULL, "doi_role" varchar(256) NOT NULL, "people_id_id" integer NULL, "project_id_id" integer NULL);
--
-- Create model ProjectFunders
--
CREATE TABLE "ingest_projectfunders" ("id" serial NOT NULL PRIMARY KEY, "funder_id_id" integer NULL, "project_id_id" integer NULL);
--
-- Create model ImageMetadata
--
--
-- Create model EventsLog
--
CREATE TABLE "ingest_eventslog" ("id" serial NOT NULL PRIMARY KEY, "notes" varchar(256) NOT NULL, "timestamp" timestamp with time zone NOT NULL, "event_type" varchar(64) NOT NULL, "collection_id_id" integer NULL, "people_id_id" integer NULL, "project_id_id" integer NULL);
--
-- Create model DescriptiveMetadata
--
--
-- Create model CollectionGroup
--
CREATE TABLE "ingest_collectiongroup" ("id" serial NOT NULL PRIMARY KEY, "name" varchar(256) NOT NULL, "project_id_id" integer NULL);
--
-- Add field collection_group_id to collection
--
ALTER TABLE "ingest_collection" ADD COLUMN "collection_group_id_id" integer NULL CONSTRAINT "ingest_collection_collection_group_id__a639afc4_fk_ingest_co" REFERENCES "ingest_collectiongroup"("id") DEFERRABLE INITIALLY DEFERRED; SET CONSTRAINTS "ingest_collection_collection_group_id__a639afc4_fk_ingest_co" IMMEDIATE;
--
-- Add field user to collection
--
ALTER TABLE "ingest_collection" ADD COLUMN "user_id" integer NULL CONSTRAINT "ingest_collection_user_id_09908d0f_fk_auth_user_id" REFERENCES "auth_user"("id") DEFERRABLE INITIALLY DEFERRED; SET CONSTRAINTS "ingest_collection_user_id_09908d0f_fk_auth_user_id" IMMEDIATE;
CREATE INDEX "ingest_collection_name_ce993f04_like" ON "ingest_collection" ("name" varchar_pattern_ops);
ALTER TABLE "ingest_people" ADD CONSTRAINT "ingest_people_auth_user_id_id_af2ebed4_fk_auth_user_id" FOREIGN KEY ("auth_user_id_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_people_auth_user_id_id_af2ebed4" ON "ingest_people" ("auth_user_id_id");
CREATE INDEX "ingest_uuid_useduuid_2ceca877_like" ON "ingest_uuid" ("useduuid" varchar_pattern_ops);
ALTER TABLE "ingest_projectpeople" ADD CONSTRAINT "ingest_projectpeople_people_id_id_1267e62e_fk_ingest_people_id" FOREIGN KEY ("people_id_id") REFERENCES "ingest_people" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "ingest_projectpeople" ADD CONSTRAINT "ingest_projectpeople_project_id_id_45236d01_fk_ingest_pr" FOREIGN KEY ("project_id_id") REFERENCES "ingest_project" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_projectpeople_people_id_id_1267e62e" ON "ingest_projectpeople" ("people_id_id");
CREATE INDEX "ingest_projectpeople_project_id_id_45236d01" ON "ingest_projectpeople" ("project_id_id");
ALTER TABLE "ingest_projectfunders" ADD CONSTRAINT "ingest_projectfunders_funder_id_id_f6e4421c_fk_ingest_funder_id" FOREIGN KEY ("funder_id_id") REFERENCES "ingest_funder" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "ingest_projectfunders" ADD CONSTRAINT "ingest_projectfunder_project_id_id_e9670b35_fk_ingest_pr" FOREIGN KEY ("project_id_id") REFERENCES "ingest_project" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_projectfunders_funder_id_id_f6e4421c" ON "ingest_projectfunders" ("funder_id_id");
CREATE INDEX "ingest_projectfunders_project_id_id_e9670b35" ON "ingest_projectfunders" ("project_id_id");
ALTER TABLE "ingest_imagemetadata" ADD CONSTRAINT "ingest_imagemetadata_collection_id_36dc62ee_fk_ingest_co" FOREIGN KEY ("collection_id") REFERENCES "ingest_collection" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "ingest_imagemetadata" ADD CONSTRAINT "ingest_imagemetadata_user_id_bfbf7eaf_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_imagemetadata_collection_id_36dc62ee" ON "ingest_imagemetadata" ("collection_id");
CREATE INDEX "ingest_imagemetadata_user_id_bfbf7eaf" ON "ingest_imagemetadata" ("user_id");
ALTER TABLE "ingest_eventslog" ADD CONSTRAINT "ingest_eventslog_collection_id_id_9da5c007_fk_ingest_co" FOREIGN KEY ("collection_id_id") REFERENCES "ingest_collection" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "ingest_eventslog" ADD CONSTRAINT "ingest_eventslog_people_id_id_38b2340f_fk_ingest_people_id" FOREIGN KEY ("people_id_id") REFERENCES "ingest_people" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "ingest_eventslog" ADD CONSTRAINT "ingest_eventslog_project_id_id_3cc0901c_fk_ingest_project_id" FOREIGN KEY ("project_id_id") REFERENCES "ingest_project" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_eventslog_collection_id_id_9da5c007" ON "ingest_eventslog" ("collection_id_id");
CREATE INDEX "ingest_eventslog_people_id_id_38b2340f" ON "ingest_eventslog" ("people_id_id");
CREATE INDEX "ingest_eventslog_project_id_id_3cc0901c" ON "ingest_eventslog" ("project_id_id");
ALTER TABLE "ingest_descriptivemetadata" ADD CONSTRAINT "ingest_descriptiveme_collection_id_4c5f96f3_fk_ingest_co" FOREIGN KEY ("collection_id") REFERENCES "ingest_collection" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "ingest_descriptivemetadata" ADD CONSTRAINT "ingest_descriptivemetadata_user_id_7f0b3940_fk_auth_user_id" FOREIGN KEY ("user_id") REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_descriptivemetadata_collection_id_4c5f96f3" ON "ingest_descriptivemetadata" ("collection_id");
CREATE INDEX "ingest_descriptivemetadata_user_id_7f0b3940" ON "ingest_descriptivemetadata" ("user_id");
ALTER TABLE "ingest_collectiongroup" ADD CONSTRAINT "ingest_collectiongro_project_id_id_86a64d1a_fk_ingest_pr" FOREIGN KEY ("project_id_id") REFERENCES "ingest_project" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "ingest_collectiongroup_project_id_id_86a64d1a" ON "ingest_collectiongroup" ("project_id_id");
CREATE INDEX "ingest_collection_collection_group_id_id_a639afc4" ON "ingest_collection" ("collection_group_id_id");
CREATE INDEX "ingest_collection_user_id_09908d0f" ON "ingest_collection" ("user_id");
ROLLBACK;
