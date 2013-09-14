--
-- Database scheme for stargate queue plugin integration.
--

-- ------------------------------------------------------------------

SET SQL_MODE="NO_AUTO_VALUE_ON_ZERO";

--
-- Database: `stargate`
--
-- CREATE DATABASE stargate;
-- USE stargate;

-- --------------------------------------------------------

--
-- Table structure for table `queue`
--

CREATE TABLE IF NOT EXISTS `queue` (
    `id` int(11) NOT NULL auto_increment,
    `uid` varchar(32) NOT NULL default '',
    `callback` smallint(3) NOT NULL default '0',
    `callerid` varchar(15) NOT NULL default '',
    `number` varchar(15) default NULL,
    `room` varchar(11) default NULL,
    `queue_name` varchar(20) default NULL,
    `count` int(3) NOT NULL default '0',
    PRIMARY KEY  (`id`),
    UNIQUE KEY `Unique ID` (`uid`),
    KEY `callback` (`callback`)
) ENGINE=MyISAM  DEFAULT CHARSET=latin1;


-- --------------------------------------------------------

--
-- Table structure for table `callback_blacklist`
--

CREATE TABLE IF NOT EXISTS `callback_blacklist` (
    `id` int(11) NOT NULL auto_increment,
    `number` varchar(15) NOT NULL default '',
    PRIMARY KEY  (`id`),
    KEY `callbacknum` (`number`)
) ENGINE=MyISAM  DEFAULT CHARSET=latin1 COMMENT='Collection of numbers
not allowed for customer callback' AUTO_INCREMENT=100;

--
-- Dumping data for table `callback_blacklist`
--

INSERT INTO `callback_blacklist` (`id`, `number`) VALUES
(1, '911'),
(2, '411');


-- ------------------------------------------------------

--
-- Table structure for table `queue_members`
--

CREATE TABLE IF NOT EXISTS `queue_members` (
    `agent` int(11) NOT NULL default '0',
    `queue` varchar(128) NOT NULL default '',
    `name` varchar(128) default NULL,
    `location` varchar(128) NOT NULL default '',
    `penalty` int(11) default NULL,
    `calls_taken` int(32) NOT NULL default '0',
    `last_call` varchar(32) NOT NULL default '',
    `status` int(4) NOT NULL default '0',
    `paused` tinyint(1) NOT NULL default '0',
    `timestamp` timestamp NULL default CURRENT_TIMESTAMP,
    PRIMARY KEY  (`queue`,`location`)
) ENGINE=MyISAM DEFAULT CHARSET=latin1;


