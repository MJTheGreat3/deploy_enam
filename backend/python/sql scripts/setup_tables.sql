
-- ======================================================
-- CREATE TABLES
-- ======================================================

-- announcements
CREATE TABLE announcements (
    Stock TEXT,
    Subject TEXT,
    Announcement TEXT,
    Attachment TEXT,
    Time TIMESTAMP
);

-- block_deals
CREATE TABLE block_deals (
    Source TEXT,
    Deal_Date TEXT,
    Security_Name TEXT,
    Client_Name TEXT,
    Deal_Type TEXT,
    Quantity TEXT,
    Trade_Price TEXT
);

-- bulk_deals
CREATE TABLE bulk_deals (
    Source TEXT,
    Deal_Date TEXT,
    Security_Name TEXT,
    Client_Name TEXT,
    Deal_Type TEXT,
    Quantity TEXT,
    Price TEXT
);

-- actions (as before)
CREATE TABLE corp_actions (
    Security_Code TEXT,
    Security_Name TEXT,
    Company_Name TEXT,
    Ex_Date DATE,
    Purpose TEXT,
    Record_Date DATE,
    BC_Start_Date DATE,
    BC_End_Date DATE,
    ND_Start_Date DATE,
    ND_End_Date DATE,
    Actual_Payment_Date DATE
);

-- deliv_deviation (as before)
CREATE TABLE deliv_deviation (
    SYMBOL TEXT,
    AVG_DELIV_QTY TEXT,
    NEW_DELIV_QTY TEXT,
    PCT_DEVIATION NUMERIC
);

-- insider_trading
CREATE TABLE insider_trading (
    Stock TEXT,
    Clause TEXT,
    Name TEXT,
    Type TEXT,
    Amount TEXT,
    Value TEXT,
    Transaction TEXT,
    Attachment TEXT,
    Time TEXT
);

-- master (as before)
CREATE TABLE master (
    SYMBOL TEXT,
    AVG_TTL_TRD_QNTY TEXT,
    AVG_DELIV_QTY TEXT
);

-- symbols (as before)
CREATE TABLE symbols (
    Symbol TEXT,
    Name TEXT
);

-- vol_deviation (as before)
CREATE TABLE vol_deviation (
    SYMBOL TEXT,
    AVG_TTL_TRD_QNTY TEXT,
    NEW_TTL_TRD_QNTY TEXT,
    PCT_DEVIATION NUMERIC
);