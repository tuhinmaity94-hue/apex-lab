-- Apex Lab schema baseline v1. Generated from backend/models.py.

PRAGMA foreign_keys=ON;

CREATE TABLE user (
	id INTEGER NOT NULL, 
	username VARCHAR(40) NOT NULL, 
	password_hash VARCHAR(256) NOT NULL, 
	role VARCHAR(16) NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);

CREATE TABLE season (
	id INTEGER NOT NULL, 
	number INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (number)
);

CREATE TABLE weapon (
	id INTEGER NOT NULL, 
	slug VARCHAR(50) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	category VARCHAR(30) NOT NULL, 
	ammo VARCHAR(30) NOT NULL, 
	image VARCHAR(240) NOT NULL, 
	image_source VARCHAR(500) NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (slug)
);

CREATE INDEX ix_weapon_category ON weapon (category);

CREATE TABLE schema_version (
	version INTEGER NOT NULL, 
	applied_at DATETIME NOT NULL, 
	PRIMARY KEY (version)
);

CREATE TABLE patch (
	id INTEGER NOT NULL, 
	season_id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	released_at DATE NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(season_id) REFERENCES season (id), 
	UNIQUE (name)
);

CREATE TABLE "match" (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	played_at DATE NOT NULL, 
	map_name VARCHAR(50) NOT NULL, 
	legend VARCHAR(50) NOT NULL, 
	placement INTEGER NOT NULL, 
	kills INTEGER NOT NULL, 
	damage INTEGER NOT NULL, 
	rp INTEGER NOT NULL, 
	note VARCHAR(1000) NOT NULL, 
	is_sample BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT ck_match_values CHECK (placement BETWEEN 1 AND 20 AND kills >= 0 AND damage >= 0), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);

CREATE INDEX ix_match_user_date ON "match" (user_id, played_at);

CREATE TABLE favorite (
	id INTEGER NOT NULL, 
	user_id INTEGER NOT NULL, 
	weapon_id INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_favorite UNIQUE (user_id, weapon_id), 
	FOREIGN KEY(user_id) REFERENCES user (id), 
	FOREIGN KEY(weapon_id) REFERENCES weapon (id)
);

CREATE TABLE audit (
	id INTEGER NOT NULL, 
	user_id INTEGER, 
	action VARCHAR(100) NOT NULL, 
	detail TEXT NOT NULL, 
	created_at DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(user_id) REFERENCES user (id)
);

CREATE TABLE weapon_stat (
	id INTEGER NOT NULL, 
	weapon_id INTEGER NOT NULL, 
	patch_id INTEGER NOT NULL, 
	body FLOAT NOT NULL, 
	head FLOAT NOT NULL, 
	leg FLOAT NOT NULL, 
	rpm FLOAT NOT NULL, 
	pellets INTEGER NOT NULL, 
	reload_time FLOAT NOT NULL, 
	startup FLOAT NOT NULL, 
	burst_size INTEGER NOT NULL, 
	burst_delay FLOAT NOT NULL, 
	status VARCHAR(20) NOT NULL, 
	source_url VARCHAR(500) NOT NULL, 
	note TEXT NOT NULL, 
	revision INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_weapon_patch UNIQUE (weapon_id, patch_id), 
	CONSTRAINT ck_positive_damage_rate CHECK (body > 0 AND head > 0 AND leg > 0 AND rpm > 0), 
	CONSTRAINT ck_timing CHECK (reload_time > 0 AND pellets > 0 AND startup >= 0), 
	FOREIGN KEY(weapon_id) REFERENCES weapon (id), 
	FOREIGN KEY(patch_id) REFERENCES patch (id)
);

CREATE INDEX ix_weapon_stat_patch_id ON weapon_stat (patch_id);

CREATE TABLE match_weapon (
	id INTEGER NOT NULL, 
	match_id INTEGER NOT NULL, 
	weapon_id INTEGER NOT NULL, 
	slot INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_match_slot UNIQUE (match_id, slot), 
	FOREIGN KEY(match_id) REFERENCES "match" (id) ON DELETE CASCADE, 
	FOREIGN KEY(weapon_id) REFERENCES weapon (id)
);

CREATE TABLE magazine (
	id INTEGER NOT NULL, 
	stat_id INTEGER NOT NULL, 
	tier INTEGER NOT NULL, 
	capacity INTEGER NOT NULL, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_magazine_tier UNIQUE (stat_id, tier), 
	CONSTRAINT ck_magazine CHECK (capacity > 0 AND tier >= 0 AND tier <= 3), 
	FOREIGN KEY(stat_id) REFERENCES weapon_stat (id) ON DELETE CASCADE
);
