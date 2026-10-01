-- MySQL dump 10.13  Distrib 8.4.11, for Linux (x86_64)
--
-- Host: db    Database: educatief_epd
-- ------------------------------------------------------
-- Server version	8.4.11

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Table structure for table `auth_group`
--

DROP TABLE IF EXISTS `auth_group`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group`
--

LOCK TABLES `auth_group` WRITE;
/*!40000 ALTER TABLE `auth_group` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_group_permissions`
--

DROP TABLE IF EXISTS `auth_group_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_group_permissions`
--

LOCK TABLES `auth_group_permissions` WRITE;
/*!40000 ALTER TABLE `auth_group_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_group_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_permission`
--

DROP TABLE IF EXISTS `auth_permission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=73 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_permission`
--

LOCK TABLES `auth_permission` WRITE;
/*!40000 ALTER TABLE `auth_permission` DISABLE KEYS */;
INSERT INTO `auth_permission` VALUES (1,'Can add log entry',1,'add_logentry'),(2,'Can change log entry',1,'change_logentry'),(3,'Can delete log entry',1,'delete_logentry'),(4,'Can view log entry',1,'view_logentry'),(5,'Can add permission',2,'add_permission'),(6,'Can change permission',2,'change_permission'),(7,'Can delete permission',2,'delete_permission'),(8,'Can view permission',2,'view_permission'),(9,'Can add group',3,'add_group'),(10,'Can change group',3,'change_group'),(11,'Can delete group',3,'delete_group'),(12,'Can view group',3,'view_group'),(13,'Can add user',4,'add_user'),(14,'Can change user',4,'change_user'),(15,'Can delete user',4,'delete_user'),(16,'Can view user',4,'view_user'),(17,'Can add content type',5,'add_contenttype'),(18,'Can change content type',5,'change_contenttype'),(19,'Can delete content type',5,'delete_contenttype'),(20,'Can view content type',5,'view_contenttype'),(21,'Can add session',6,'add_session'),(22,'Can change session',6,'change_session'),(23,'Can delete session',6,'delete_session'),(24,'Can view session',6,'view_session'),(25,'Can add case',7,'add_case'),(26,'Can change case',7,'change_case'),(27,'Can delete case',7,'delete_case'),(28,'Can view case',7,'view_case'),(29,'Can add patient',8,'add_patient'),(30,'Can change patient',8,'change_patient'),(31,'Can delete patient',8,'delete_patient'),(32,'Can view patient',8,'view_patient'),(33,'Can add assignment',9,'add_assignment'),(34,'Can change assignment',9,'change_assignment'),(35,'Can delete assignment',9,'delete_assignment'),(36,'Can view assignment',9,'view_assignment'),(37,'Can add module',10,'add_module'),(38,'Can change module',10,'change_module'),(39,'Can delete module',10,'delete_module'),(40,'Can view module',10,'view_module'),(41,'Can add profile',11,'add_profile'),(42,'Can change profile',11,'change_profile'),(43,'Can delete profile',11,'delete_profile'),(44,'Can view profile',11,'view_profile'),(45,'Can add student case',12,'add_studentcase'),(46,'Can change student case',12,'change_studentcase'),(47,'Can delete student case',12,'delete_studentcase'),(48,'Can view student case',12,'view_studentcase'),(49,'Can add module response',13,'add_moduleresponse'),(50,'Can change module response',13,'change_moduleresponse'),(51,'Can delete module response',13,'delete_moduleresponse'),(52,'Can view module response',13,'view_moduleresponse'),(53,'Can add assignment submission',14,'add_assignmentsubmission'),(54,'Can change assignment submission',14,'change_assignmentsubmission'),(55,'Can delete assignment submission',14,'delete_assignmentsubmission'),(56,'Can view assignment submission',14,'view_assignmentsubmission'),(57,'Can add audit event',15,'add_auditevent'),(58,'Can change audit event',15,'change_auditevent'),(59,'Can delete audit event',15,'delete_auditevent'),(60,'Can view audit event',15,'view_auditevent'),(61,'Can add library template',16,'add_librarytemplate'),(62,'Can change library template',16,'change_librarytemplate'),(63,'Can delete library template',16,'delete_librarytemplate'),(64,'Can view library template',16,'view_librarytemplate'),(65,'Can add library field',17,'add_libraryfield'),(66,'Can change library field',17,'change_libraryfield'),(67,'Can delete library field',17,'delete_libraryfield'),(68,'Can view library field',17,'view_libraryfield'),(69,'Can add module field',18,'add_modulefield'),(70,'Can change module field',18,'change_modulefield'),(71,'Can delete module field',18,'delete_modulefield'),(72,'Can view module field',18,'view_modulefield');
/*!40000 ALTER TABLE `auth_permission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user`
--

DROP TABLE IF EXISTS `auth_user`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) NOT NULL,
  `first_name` varchar(150) NOT NULL,
  `last_name` varchar(150) NOT NULL,
  `email` varchar(254) NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user`
--

LOCK TABLES `auth_user` WRITE;
/*!40000 ALTER TABLE `auth_user` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_groups`
--

DROP TABLE IF EXISTS `auth_user_groups`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_groups`
--

LOCK TABLES `auth_user_groups` WRITE;
/*!40000 ALTER TABLE `auth_user_groups` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_groups` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `auth_user_user_permissions`
--

DROP TABLE IF EXISTS `auth_user_user_permissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `auth_user_user_permissions`
--

LOCK TABLES `auth_user_user_permissions` WRITE;
/*!40000 ALTER TABLE `auth_user_user_permissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `auth_user_user_permissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_admin_log`
--

DROP TABLE IF EXISTS `django_admin_log`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext,
  `object_repr` varchar(200) NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_admin_log`
--

LOCK TABLES `django_admin_log` WRITE;
/*!40000 ALTER TABLE `django_admin_log` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_admin_log` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_content_type`
--

DROP TABLE IF EXISTS `django_content_type`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) NOT NULL,
  `model` varchar(100) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=19 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_content_type`
--

LOCK TABLES `django_content_type` WRITE;
/*!40000 ALTER TABLE `django_content_type` DISABLE KEYS */;
INSERT INTO `django_content_type` VALUES (1,'admin','logentry'),(3,'auth','group'),(2,'auth','permission'),(4,'auth','user'),(5,'contenttypes','contenttype'),(9,'dossier','assignment'),(14,'dossier','assignmentsubmission'),(15,'dossier','auditevent'),(7,'dossier','case'),(17,'dossier','libraryfield'),(16,'dossier','librarytemplate'),(10,'dossier','module'),(18,'dossier','modulefield'),(13,'dossier','moduleresponse'),(8,'dossier','patient'),(11,'dossier','profile'),(12,'dossier','studentcase'),(6,'sessions','session');
/*!40000 ALTER TABLE `django_content_type` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_migrations`
--

DROP TABLE IF EXISTS `django_migrations`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) NOT NULL,
  `name` varchar(255) NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_migrations`
--

LOCK TABLES `django_migrations` WRITE;
/*!40000 ALTER TABLE `django_migrations` DISABLE KEYS */;
INSERT INTO `django_migrations` VALUES (1,'contenttypes','0001_initial','2026-09-24 13:29:16.962672'),(2,'auth','0001_initial','2026-09-24 13:29:19.021718'),(3,'admin','0001_initial','2026-09-24 13:29:19.523784'),(4,'admin','0002_logentry_remove_auto_add','2026-09-24 13:29:19.536367'),(5,'admin','0003_logentry_add_action_flag_choices','2026-09-24 13:29:19.554646'),(6,'contenttypes','0002_remove_content_type_name','2026-09-24 13:29:19.899182'),(7,'auth','0002_alter_permission_name_max_length','2026-09-24 13:29:20.118000'),(8,'auth','0003_alter_user_email_max_length','2026-09-24 13:29:20.170069'),(9,'auth','0004_alter_user_username_opts','2026-09-24 13:29:20.188857'),(10,'auth','0005_alter_user_last_login_null','2026-09-24 13:29:20.386444'),(11,'auth','0006_require_contenttypes_0002','2026-09-24 13:29:20.397836'),(12,'auth','0007_alter_validators_add_error_messages','2026-09-24 13:29:20.413484'),(13,'auth','0008_alter_user_username_max_length','2026-09-24 13:29:20.635088'),(14,'auth','0009_alter_user_last_name_max_length','2026-09-24 13:29:20.850944'),(15,'auth','0010_alter_group_name_max_length','2026-09-24 13:29:20.892667'),(16,'auth','0011_update_proxy_permissions','2026-09-24 13:29:20.908189'),(17,'auth','0012_alter_user_first_name_max_length','2026-09-24 13:29:21.126142'),(18,'dossier','0001_initial','2026-09-24 13:29:22.014093'),(19,'dossier','0002_assignment_content','2026-09-24 13:29:22.207198'),(20,'dossier','0003_remove_assignment_status_case_created_by_and_more','2026-09-24 13:29:26.329381'),(21,'dossier','0004_alter_assignmentsubmission_options_and_more','2026-09-24 13:29:36.294757'),(22,'sessions','0001_initial','2026-09-24 13:29:36.418454');
/*!40000 ALTER TABLE `django_migrations` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `django_session`
--

DROP TABLE IF EXISTS `django_session`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `django_session` (
  `session_key` varchar(40) NOT NULL,
  `session_data` longtext NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `django_session`
--

LOCK TABLES `django_session` WRITE;
/*!40000 ALTER TABLE `django_session` DISABLE KEYS */;
/*!40000 ALTER TABLE `django_session` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_assignment`
--

DROP TABLE IF EXISTS `dossier_assignment`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_assignment` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(240) NOT NULL,
  `phase` varchar(120) NOT NULL,
  `position` int unsigned NOT NULL,
  `case_id` bigint NOT NULL,
  `content` longtext NOT NULL,
  PRIMARY KEY (`id`),
  KEY `dossier_assignment_case_id_be69eae0_fk_dossier_case_id` (`case_id`),
  CONSTRAINT `dossier_assignment_case_id_be69eae0_fk_dossier_case_id` FOREIGN KEY (`case_id`) REFERENCES `dossier_case` (`id`),
  CONSTRAINT `dossier_assignment_chk_1` CHECK ((`position` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_assignment`
--

LOCK TABLES `dossier_assignment` WRITE;
/*!40000 ALTER TABLE `dossier_assignment` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_assignment` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_assignmentsubmission`
--

DROP TABLE IF EXISTS `dossier_assignmentsubmission`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_assignmentsubmission` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `answer` longtext NOT NULL,
  `status` varchar(20) NOT NULL,
  `submitted_at` datetime(6) DEFAULT NULL,
  `updated_at` datetime(6) NOT NULL,
  `assignment_id` bigint DEFAULT NULL,
  `student_case_id` bigint NOT NULL,
  `content` longtext NOT NULL,
  `feedback` longtext NOT NULL,
  `phase` varchar(120) NOT NULL,
  `position` int unsigned NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `title` varchar(240) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_assignment_submission` (`student_case_id`,`assignment_id`),
  KEY `dossier_assignmentsu_assignment_id_50235d10_fk_dossier_a` (`assignment_id`),
  CONSTRAINT `dossier_assignmentsu_assignment_id_50235d10_fk_dossier_a` FOREIGN KEY (`assignment_id`) REFERENCES `dossier_assignment` (`id`),
  CONSTRAINT `dossier_assignmentsu_student_case_id_b9bd4204_fk_dossier_s` FOREIGN KEY (`student_case_id`) REFERENCES `dossier_studentcase` (`id`),
  CONSTRAINT `dossier_assignmentsubmission_chk_1` CHECK ((`position` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_assignmentsubmission`
--

LOCK TABLES `dossier_assignmentsubmission` WRITE;
/*!40000 ALTER TABLE `dossier_assignmentsubmission` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_assignmentsubmission` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_auditevent`
--

DROP TABLE IF EXISTS `dossier_auditevent`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_auditevent` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `action` varchar(80) NOT NULL,
  `target_type` varchar(80) NOT NULL,
  `target_id` varchar(80) NOT NULL,
  `details` json NOT NULL,
  `ip_address` char(39) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `actor_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dossier_auditevent_actor_id_502fe59c_fk_auth_user_id` (`actor_id`),
  CONSTRAINT `dossier_auditevent_actor_id_502fe59c_fk_auth_user_id` FOREIGN KEY (`actor_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_auditevent`
--

LOCK TABLES `dossier_auditevent` WRITE;
/*!40000 ALTER TABLE `dossier_auditevent` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_auditevent` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_case`
--

DROP TABLE IF EXISTS `dossier_case`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_case` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(180) NOT NULL,
  `course` varchar(180) NOT NULL,
  `patient_id` bigint NOT NULL,
  `created_by_id` int DEFAULT NULL,
  `introduction` longtext NOT NULL,
  `learning_objectives` longtext NOT NULL,
  `published_at` datetime(6) DEFAULT NULL,
  `archived_at` datetime(6) DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `status` varchar(20) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `dossier_case_patient_id_77a0d2bf_uniq` (`patient_id`),
  KEY `dossier_case_created_by_id_e9d3bced_fk_auth_user_id` (`created_by_id`),
  CONSTRAINT `dossier_case_created_by_id_e9d3bced_fk_auth_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `dossier_case_patient_id_77a0d2bf_fk_dossier_patient_id` FOREIGN KEY (`patient_id`) REFERENCES `dossier_patient` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_case`
--

LOCK TABLES `dossier_case` WRITE;
/*!40000 ALTER TABLE `dossier_case` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_case` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_libraryfield`
--

DROP TABLE IF EXISTS `dossier_libraryfield`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_libraryfield` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `label` varchar(180) NOT NULL,
  `key` varchar(80) NOT NULL,
  `field_type` varchar(24) NOT NULL,
  `help_text` varchar(280) NOT NULL,
  `required` tinyint(1) NOT NULL,
  `position` int unsigned NOT NULL,
  `options` json NOT NULL,
  `rows` json NOT NULL,
  `columns` json NOT NULL,
  `template_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_library_field_key` (`template_id`,`key`),
  KEY `dossier_libraryfield_key_cc855404` (`key`),
  CONSTRAINT `dossier_libraryfield_template_id_7f72d8ab_fk_dossier_l` FOREIGN KEY (`template_id`) REFERENCES `dossier_librarytemplate` (`id`),
  CONSTRAINT `dossier_libraryfield_chk_1` CHECK ((`position` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=30 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_libraryfield`
--

LOCK TABLES `dossier_libraryfield` WRITE;
/*!40000 ALTER TABLE `dossier_libraryfield` DISABLE KEYS */;
INSERT INTO `dossier_libraryfield` VALUES (1,'Reden van opname','veld-1','long_text','',0,0,'[]','[]','[]',2),(2,'Huidige klachten en symptomen','veld-2','long_text','',0,1,'[]','[]','[]',2),(3,'Medische voorgeschiedenis','veld-3','long_text','',0,2,'[]','[]','[]',2),(4,'Allergieën','veld-4','long_text','',0,3,'[]','[]','[]',2),(5,'Medicatie','veld-5','long_text','',0,4,'[]','[]','[]',2),(6,'Obstetrische voorgeschiedenis','veld-6','long_text','',0,5,'[]','[]','[]',2),(7,'Zwangerschapsduur (weken)','veld-1','number','',0,0,'[]','[]','[]',3),(8,'Uitgerekende datum','veld-2','date','',0,1,'[]','[]','[]',3),(9,'Gravida','veld-3','number','',0,2,'[]','[]','[]',3),(10,'Para','veld-4','number','',0,3,'[]','[]','[]',3),(11,'Risicofactoren','veld-5','long_text','',0,4,'[]','[]','[]',3),(12,'Start contracties','veld-1','datetime','',0,0,'[]','[]','[]',4),(13,'Vliezen gebroken','veld-2','datetime','',0,1,'[]','[]','[]',4),(14,'Ontsluiting (cm)','veld-3','number','',0,2,'[]','[]','[]',4),(15,'Foetale hartfrequentie','veld-4','number','',0,3,'[]','[]','[]',4),(16,'Klinische observaties','veld-5','observation','',0,4,'[]','[]','[]',4),(17,'Indicatie','veld-1','long_text','',0,0,'[]','[]','[]',5),(18,'Opnamedatum','veld-2','date','',0,1,'[]','[]','[]',5),(19,'Observaties','veld-3','observation','',0,2,'[]','[]','[]',5),(20,'Bloedverlies (ml)','veld-1','number','',0,0,'[]','[]','[]',6),(21,'Toestand moeder en kind','veld-2','long_text','',0,1,'[]','[]','[]',6),(22,'Observaties','veld-3','observation','',0,2,'[]','[]','[]',6),(23,'Verslag','veld-1','long_text','',0,0,'[]','[]','[]',7),(24,'Indicatie','veld-1','long_text','',0,0,'[]','[]','[]',8),(25,'Neonatale observaties','veld-2','observation','',0,1,'[]','[]','[]',8),(26,'Actuele beleving','veld-1','long_text','',0,0,'[]','[]','[]',9),(27,'Signalen of aandachtspunten','veld-2','long_text','',0,1,'[]','[]','[]',9),(28,'Klinisch redeneerplan','matrix-1','matrix','',0,0,'[]','[\"Probleem of diagnose\", \"Gewenst resultaat\", \"Interventie\", \"Evaluatie\"]','[\"Beschrijving\", \"Motivatie\"]',10),(29,'Uitwerking','veld-1','long_text','',0,0,'[]','[]','[]',11);
/*!40000 ALTER TABLE `dossier_libraryfield` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_librarytemplate`
--

DROP TABLE IF EXISTS `dossier_librarytemplate`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_librarytemplate` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(180) NOT NULL,
  `description` longtext NOT NULL,
  `category` varchar(24) NOT NULL,
  `education` varchar(120) NOT NULL,
  `theme` varchar(120) NOT NULL,
  `instructions` longtext NOT NULL,
  `version` int unsigned NOT NULL,
  `is_fixed` tinyint(1) NOT NULL,
  `status` varchar(20) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `created_by_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dossier_librarytemplate_created_by_id_61a579f0_fk_auth_user_id` (`created_by_id`),
  CONSTRAINT `dossier_librarytemplate_created_by_id_61a579f0_fk_auth_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `dossier_librarytemplate_chk_1` CHECK ((`version` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_librarytemplate`
--

LOCK TABLES `dossier_librarytemplate` WRITE;
/*!40000 ALTER TABLE `dossier_librarytemplate` DISABLE KEYS */;
INSERT INTO `dossier_librarytemplate` VALUES (1,'Dashboard','Samenvatting van de fictieve patiënt.','module','Vroedkunde','Algemeen','',1,1,'active','2026-09-24 13:29:37.221275','2026-09-24 13:29:37.221303',NULL),(2,'Anamnese','Klachten, symptomen en relevante voorgeschiedenis.','questionnaire','Vroedkunde','Opname','',1,1,'active','2026-09-24 13:29:37.224963','2026-09-24 13:29:37.224981',NULL),(3,'Zwangerschapsdossier','Basisgegevens van de zwangerschap.','module','Vroedkunde','Zwangerschap','',1,1,'active','2026-09-24 13:29:37.229273','2026-09-24 13:29:37.229295',NULL),(4,'Partusdossier','Registratie van arbeid en bevalling.','module','Vroedkunde','Partus','',1,1,'active','2026-09-24 13:29:37.232742','2026-09-24 13:29:37.232757',NULL),(5,'MIC dossier','Maternal intensive care registratie.','module','Vroedkunde','Risicozorg','',1,1,'active','2026-09-24 13:29:37.236102','2026-09-24 13:29:37.236125',NULL),(6,'Postpartumdossier','Opvolging na de bevalling.','module','Vroedkunde','Postpartum','',1,1,'active','2026-09-24 13:29:37.239042','2026-09-24 13:29:37.239060',NULL),(7,'Kort verslag graviditeit, partus en postpartum','Beknopt klinisch verslag.','module','Vroedkunde','Verslag','',1,1,'active','2026-09-24 13:29:37.241355','2026-09-24 13:29:37.241374',NULL),(8,'NICU / N*-dossier','Registratie voor neonatale opvolging.','module','Vroedkunde','Neonatologie','',1,1,'active','2026-09-24 13:29:37.244245','2026-09-24 13:29:37.244274',NULL),(9,'Screening emotioneel welzijn','Screening van het emotioneel welzijn.','questionnaire','Vroedkunde','Welzijn','',1,1,'active','2026-09-24 13:29:37.247185','2026-09-24 13:29:37.247199',NULL),(10,'Klinisch redeneerplan','Gestructureerd zorg- en redeneerplan.','matrix','Vroedkunde','Klinisch redeneren','',1,1,'active','2026-09-24 13:29:37.249751','2026-09-24 13:29:37.249772',NULL),(11,'Uitwerking opdracht','Vrije uitwerking van de onderwijsopdracht.','module','Vroedkunde','Opdrachten','',1,1,'active','2026-09-24 13:29:37.252174','2026-09-24 13:29:37.252189',NULL);
/*!40000 ALTER TABLE `dossier_librarytemplate` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_module`
--

DROP TABLE IF EXISTS `dossier_module`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_module` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `title` varchar(180) NOT NULL,
  `position` int unsigned NOT NULL,
  `case_id` bigint NOT NULL,
  `configuration` json NOT NULL DEFAULT (_utf8mb4'{}'),
  `instructions` longtext NOT NULL,
  `kind` varchar(24) NOT NULL,
  `base_data` json NOT NULL DEFAULT (_utf8mb4'{}'),
  `source_template_version` int unsigned DEFAULT NULL,
  `source_template_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `dossier_module_case_id_746108ac_fk_dossier_case_id` (`case_id`),
  KEY `dossier_module_source_template_id_12fa8858_fk_dossier_l` (`source_template_id`),
  CONSTRAINT `dossier_module_case_id_746108ac_fk_dossier_case_id` FOREIGN KEY (`case_id`) REFERENCES `dossier_case` (`id`),
  CONSTRAINT `dossier_module_source_template_id_12fa8858_fk_dossier_l` FOREIGN KEY (`source_template_id`) REFERENCES `dossier_librarytemplate` (`id`),
  CONSTRAINT `dossier_module_chk_1` CHECK ((`position` >= 0)),
  CONSTRAINT `dossier_module_chk_2` CHECK ((`source_template_version` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_module`
--

LOCK TABLES `dossier_module` WRITE;
/*!40000 ALTER TABLE `dossier_module` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_module` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_modulefield`
--

DROP TABLE IF EXISTS `dossier_modulefield`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_modulefield` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `label` varchar(180) NOT NULL,
  `key` varchar(80) NOT NULL,
  `field_type` varchar(24) NOT NULL,
  `help_text` varchar(280) NOT NULL,
  `required` tinyint(1) NOT NULL,
  `position` int unsigned NOT NULL,
  `options` json NOT NULL,
  `rows` json NOT NULL,
  `columns` json NOT NULL,
  `module_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_module_field_key` (`module_id`,`key`),
  KEY `dossier_modulefield_key_2d55b293` (`key`),
  CONSTRAINT `dossier_modulefield_module_id_304ade1e_fk_dossier_module_id` FOREIGN KEY (`module_id`) REFERENCES `dossier_module` (`id`),
  CONSTRAINT `dossier_modulefield_chk_1` CHECK ((`position` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_modulefield`
--

LOCK TABLES `dossier_modulefield` WRITE;
/*!40000 ALTER TABLE `dossier_modulefield` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_modulefield` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_moduleresponse`
--

DROP TABLE IF EXISTS `dossier_moduleresponse`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_moduleresponse` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `data` json NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `module_id` bigint DEFAULT NULL,
  `student_case_id` bigint NOT NULL,
  `instructions` longtext NOT NULL,
  `kind` varchar(24) NOT NULL,
  `position` int unsigned NOT NULL,
  `schema` json NOT NULL DEFAULT (_utf8mb4'[]'),
  `title` varchar(180) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_module_response` (`student_case_id`,`module_id`),
  KEY `dossier_moduleresponse_module_id_daa1094d_fk_dossier_module_id` (`module_id`),
  CONSTRAINT `dossier_modulerespon_student_case_id_28cb3471_fk_dossier_s` FOREIGN KEY (`student_case_id`) REFERENCES `dossier_studentcase` (`id`),
  CONSTRAINT `dossier_moduleresponse_module_id_daa1094d_fk_dossier_module_id` FOREIGN KEY (`module_id`) REFERENCES `dossier_module` (`id`),
  CONSTRAINT `dossier_moduleresponse_chk_1` CHECK ((`position` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_moduleresponse`
--

LOCK TABLES `dossier_moduleresponse` WRITE;
/*!40000 ALTER TABLE `dossier_moduleresponse` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_moduleresponse` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_patient`
--

DROP TABLE IF EXISTS `dossier_patient`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_patient` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `name` varchar(120) NOT NULL,
  `reference` varchar(40) NOT NULL,
  `image` varchar(240) NOT NULL,
  `context` varchar(280) NOT NULL,
  `created_by_id` int DEFAULT NULL,
  `birth_date` date DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  `gender` varchar(20) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `reference` (`reference`),
  KEY `dossier_patient_created_by_id_b40ba469_fk_auth_user_id` (`created_by_id`),
  CONSTRAINT `dossier_patient_created_by_id_b40ba469_fk_auth_user_id` FOREIGN KEY (`created_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_patient`
--

LOCK TABLES `dossier_patient` WRITE;
/*!40000 ALTER TABLE `dossier_patient` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_patient` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_profile`
--

DROP TABLE IF EXISTS `dossier_profile`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_profile` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `role` varchar(20) NOT NULL,
  `user_id` int NOT NULL,
  `education` varchar(120) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `user_id` (`user_id`),
  CONSTRAINT `dossier_profile_user_id_4e481032_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_profile`
--

LOCK TABLES `dossier_profile` WRITE;
/*!40000 ALTER TABLE `dossier_profile` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_profile` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `dossier_studentcase`
--

DROP TABLE IF EXISTS `dossier_studentcase`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `dossier_studentcase` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `status` varchar(20) NOT NULL,
  `started_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `case_id` bigint NOT NULL,
  `student_id` int NOT NULL,
  `case_title` varchar(180) NOT NULL,
  `course` varchar(180) NOT NULL,
  `introduction` longtext NOT NULL,
  `learning_objectives` longtext NOT NULL,
  `patient_context` varchar(280) NOT NULL,
  `patient_image` varchar(240) NOT NULL,
  `patient_name` varchar(120) NOT NULL,
  `patient_reference` varchar(40) NOT NULL,
  `reviewed_at` datetime(6) DEFAULT NULL,
  `submitted_at` datetime(6) DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `unique_student_case` (`case_id`,`student_id`),
  KEY `dossier_studentcase_student_id_ec2c0b69_fk_auth_user_id` (`student_id`),
  CONSTRAINT `dossier_studentcase_case_id_708091fd_fk_dossier_case_id` FOREIGN KEY (`case_id`) REFERENCES `dossier_case` (`id`),
  CONSTRAINT `dossier_studentcase_student_id_ec2c0b69_fk_auth_user_id` FOREIGN KEY (`student_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `dossier_studentcase`
--

LOCK TABLES `dossier_studentcase` WRITE;
/*!40000 ALTER TABLE `dossier_studentcase` DISABLE KEYS */;
/*!40000 ALTER TABLE `dossier_studentcase` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping routines for database 'educatief_epd'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-09-24 13:37:31
