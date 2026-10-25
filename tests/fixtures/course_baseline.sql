--
-- PostgreSQL database dump
--

-- Dumped from database version 13.6 (Ubuntu 13.6-1.pgdg20.04+1)
-- Dumped by pg_dump version 13.6 (Ubuntu 13.6-1.pgdg20.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: mart; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA mart;


--
-- Name: staging; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA staging;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: d_calendar; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.d_calendar (
    date_id integer NOT NULL,
    date_actual date NOT NULL,
    epoch bigint NOT NULL,
    day_suffix character varying(4) NOT NULL,
    day_name character varying(9) NOT NULL,
    day_of_week integer NOT NULL,
    day_of_month integer NOT NULL,
    day_of_quarter integer NOT NULL,
    day_of_year integer NOT NULL,
    week_of_month integer NOT NULL,
    week_of_year integer NOT NULL,
    week_of_year_iso character(10) NOT NULL,
    month_actual integer NOT NULL,
    month_name character varying(9) NOT NULL,
    month_name_abbreviated character(3) NOT NULL,
    quarter_actual integer NOT NULL,
    quarter_name character varying(9) NOT NULL,
    year_actual integer NOT NULL,
    first_day_of_week date NOT NULL,
    last_day_of_week date NOT NULL,
    first_day_of_month date NOT NULL,
    last_day_of_month date NOT NULL,
    first_day_of_quarter date NOT NULL,
    last_day_of_quarter date NOT NULL,
    first_day_of_year date NOT NULL,
    last_day_of_year date NOT NULL,
    mmyyyy character(6) NOT NULL,
    mmddyyyy character(10) NOT NULL,
    weekend_indr boolean NOT NULL
);


--
-- Name: d_city; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.d_city (
    id integer NOT NULL,
    city_id integer,
    city_name character varying(50)
);


--
-- Name: d_city_id_seq; Type: SEQUENCE; Schema: mart; Owner: -
--

CREATE SEQUENCE mart.d_city_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: d_city_id_seq; Type: SEQUENCE OWNED BY; Schema: mart; Owner: -
--

ALTER SEQUENCE mart.d_city_id_seq OWNED BY mart.d_city.id;


--
-- Name: d_customer; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.d_customer (
    id integer NOT NULL,
    customer_id integer NOT NULL,
    first_name character varying(15),
    last_name character varying(15),
    city_id integer
);


--
-- Name: d_customer_id_seq; Type: SEQUENCE; Schema: mart; Owner: -
--

CREATE SEQUENCE mart.d_customer_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: d_customer_id_seq; Type: SEQUENCE OWNED BY; Schema: mart; Owner: -
--

ALTER SEQUENCE mart.d_customer_id_seq OWNED BY mart.d_customer.id;


--
-- Name: d_item; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.d_item (
    id integer NOT NULL,
    item_id integer NOT NULL,
    item_name character varying(50)
);


--
-- Name: d_item_id_seq; Type: SEQUENCE; Schema: mart; Owner: -
--

CREATE SEQUENCE mart.d_item_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: d_item_id_seq; Type: SEQUENCE OWNED BY; Schema: mart; Owner: -
--

ALTER SEQUENCE mart.d_item_id_seq OWNED BY mart.d_item.id;


--
-- Name: f_sales; Type: TABLE; Schema: mart; Owner: -
--

CREATE TABLE mart.f_sales (
    id integer NOT NULL,
    date_id integer NOT NULL,
    item_id integer NOT NULL,
    customer_id integer NOT NULL,
    city_id integer NOT NULL,
    quantity bigint,
    payment_amount numeric(10,2)
);


--
-- Name: f_sales_id_seq; Type: SEQUENCE; Schema: mart; Owner: -
--

CREATE SEQUENCE mart.f_sales_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: f_sales_id_seq; Type: SEQUENCE OWNED BY; Schema: mart; Owner: -
--

ALTER SEQUENCE mart.f_sales_id_seq OWNED BY mart.f_sales.id;


--
-- Name: user_order_log; Type: TABLE; Schema: staging; Owner: -
--

CREATE TABLE staging.user_order_log (
    uniq_id character varying(32) NOT NULL,
    date_time timestamp without time zone NOT NULL,
    city_id integer NOT NULL,
    city_name character varying(100),
    customer_id integer NOT NULL,
    first_name character varying(100),
    last_name character varying(100),
    item_id integer NOT NULL,
    item_name character varying(100),
    quantity bigint,
    payment_amount numeric(10,2)
);


--
-- Name: d_city id; Type: DEFAULT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_city ALTER COLUMN id SET DEFAULT nextval('mart.d_city_id_seq'::regclass);


--
-- Name: d_customer id; Type: DEFAULT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_customer ALTER COLUMN id SET DEFAULT nextval('mart.d_customer_id_seq'::regclass);


--
-- Name: d_item id; Type: DEFAULT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_item ALTER COLUMN id SET DEFAULT nextval('mart.d_item_id_seq'::regclass);


--
-- Name: f_sales id; Type: DEFAULT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.f_sales ALTER COLUMN id SET DEFAULT nextval('mart.f_sales_id_seq'::regclass);


--
-- Name: d_city d_city_city_id_key; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_city
    ADD CONSTRAINT d_city_city_id_key UNIQUE (city_id);


--
-- Name: d_city d_city_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_city
    ADD CONSTRAINT d_city_pkey PRIMARY KEY (id);


--
-- Name: d_customer d_customer_customer_id_key; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_customer
    ADD CONSTRAINT d_customer_customer_id_key UNIQUE (customer_id);


--
-- Name: d_customer d_customer_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_customer
    ADD CONSTRAINT d_customer_pkey PRIMARY KEY (id);


--
-- Name: d_calendar d_date_date_dim_id_pk; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_calendar
    ADD CONSTRAINT d_date_date_dim_id_pk PRIMARY KEY (date_id);


--
-- Name: d_item d_item_item_id_key; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_item
    ADD CONSTRAINT d_item_item_id_key UNIQUE (item_id);


--
-- Name: d_item d_item_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.d_item
    ADD CONSTRAINT d_item_pkey PRIMARY KEY (id);


--
-- Name: f_sales f_sales_pkey; Type: CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.f_sales
    ADD CONSTRAINT f_sales_pkey PRIMARY KEY (id);


--
-- Name: user_order_log user_order_log_pk; Type: CONSTRAINT; Schema: staging; Owner: -
--

ALTER TABLE ONLY staging.user_order_log
    ADD CONSTRAINT user_order_log_pk PRIMARY KEY (uniq_id);


--
-- Name: d_city1; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX d_city1 ON mart.d_city USING btree (city_id);


--
-- Name: d_cust1; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX d_cust1 ON mart.d_customer USING btree (customer_id);


--
-- Name: d_date_date_actual_idx; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX d_date_date_actual_idx ON mart.d_calendar USING btree (date_actual);


--
-- Name: d_item1; Type: INDEX; Schema: mart; Owner: -
--

CREATE UNIQUE INDEX d_item1 ON mart.d_item USING btree (item_id);


--
-- Name: f_ds1; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX f_ds1 ON mart.f_sales USING btree (date_id);


--
-- Name: f_ds2; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX f_ds2 ON mart.f_sales USING btree (item_id);


--
-- Name: f_ds3; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX f_ds3 ON mart.f_sales USING btree (customer_id);


--
-- Name: f_ds4; Type: INDEX; Schema: mart; Owner: -
--

CREATE INDEX f_ds4 ON mart.f_sales USING btree (city_id);


--
-- Name: uo1; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX uo1 ON staging.user_order_log USING btree (customer_id);


--
-- Name: uo2; Type: INDEX; Schema: staging; Owner: -
--

CREATE INDEX uo2 ON staging.user_order_log USING btree (item_id);


--
-- Name: f_sales f_sales_customer_id_fkey; Type: FK CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.f_sales
    ADD CONSTRAINT f_sales_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES mart.d_customer(customer_id);


--
-- Name: f_sales f_sales_date_id_fkey; Type: FK CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.f_sales
    ADD CONSTRAINT f_sales_date_id_fkey FOREIGN KEY (date_id) REFERENCES mart.d_calendar(date_id);


--
-- Name: f_sales f_sales_item_id_fkey; Type: FK CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.f_sales
    ADD CONSTRAINT f_sales_item_id_fkey FOREIGN KEY (item_id) REFERENCES mart.d_item(item_id);


--
-- Name: f_sales f_sales_item_id_fkey1; Type: FK CONSTRAINT; Schema: mart; Owner: -
--

ALTER TABLE ONLY mart.f_sales
    ADD CONSTRAINT f_sales_item_id_fkey1 FOREIGN KEY (item_id) REFERENCES mart.d_item(item_id);


--
-- PostgreSQL database dump complete
--
