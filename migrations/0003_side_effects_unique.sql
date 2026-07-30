ALTER TABLE side_effects
ADD CONSTRAINT unique_side_effect_per_job
UNIQUE (job_id);