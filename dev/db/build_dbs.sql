CREATE TABLE norad_list (
    id SERIAL PRIMARY KEY,
    norad_code TEXT NOT NULL,
    subscription_level TEXT NOT NULL,
    priority_level TEXT NOT NULL,
    timestamp TIMESTAMP
);

CREATE TABLE match_actual (
    id SERIAL PRIMARY KEY,
    norad_code VARCHAR(20) NOT NULL,
    sat1 VARCHAR(50) NOT NULL,
    sat2 VARCHAR(50) NOT NULL,
    time DOUBLE PRECISION NOT NULL,
    distance DOUBLE PRECISION NOT NULL,
    coord1 TEXT NOT NULL,
    coord2 TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE match_history (
    id SERIAL PRIMARY KEY,
    norad_code VARCHAR(20) NOT NULL,
    sat1 VARCHAR(50) NOT NULL,
    sat2 VARCHAR(50) NOT NULL,
    time DOUBLE PRECISION NOT NULL,
    distance DOUBLE PRECISION NOT NULL,
    coord1 TEXT NOT NULL,
    coord2 TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE tle_list (
    idcounter SERIAL PRIMARY KEY,  -- Generato automaticamente
    codnorad_riga1 INTEGER,
    classificazione CHARACTER(1),
    anno INTEGER,
    nrlancio_anno INTEGER,
    pezzo_lancio VARCHAR(255),
    annoepoca_astro INTEGER,
    epoca_astro DOUBLE PRECISION,
    derivata_prima DOUBLE PRECISION,
    derivata_seconda DOUBLE PRECISION,
    termine_trascinamento VARCHAR(255),
    tipo_effemeridi INTEGER,
    nrset INTEGER,
    chksum_riga1 INTEGER,
    codnorad_riga2 INTEGER,
    inclinazione DOUBLE PRECISION,
    ascensione_retta DOUBLE PRECISION,
    eccentricita DOUBLE PRECISION,
    arg_perigeo DOUBLE PRECISION,
    anomalia_media DOUBLE PRECISION,
    moto_medio DOUBLE PRECISION,
    nr_rivoluzioni INTEGER,
    chksum_riga2 INTEGER,
    json JSON,
    sourceid INTEGER,
    dt TIMESTAMP WITHOUT TIME ZONE,
    extra_info TEXT  -- Campo di testo per maggiore flessibilità
    APOAPSIS TEXT,
    PERIAPSIS TEXT,
    INCLINATION TEXT,
);
