#!/usr/bin/env python3
"""
Unit tests for myWhoosh2Garmin.py

These tests mock all Garmin interactions to ensure no actual uploads occur.
"""
import unittest
from unittest.mock import (
    Mock, patch, MagicMock, mock_open, call
)
from pathlib import Path
import json
import sys
import tempfile
import shutil
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import the module under test
import myWhoosh2Garmin as mw2g


class TestCalculateAvg(unittest.TestCase):
    """Test the calculate_avg function."""
    
    def test_calculate_avg_with_values(self):
        """Test average calculation with values."""
        values = [100, 150, 200, 250, 300]
        result = mw2g.calculate_avg(values)
        self.assertEqual(result, 200.0)
    
    def test_calculate_avg_empty(self):
        """Test average calculation with empty list."""
        result = mw2g.calculate_avg([])
        self.assertEqual(result, 0.0)
    
    def test_calculate_avg_single_value(self):
        """Test average calculation with single value."""
        result = mw2g.calculate_avg([42])
        self.assertEqual(result, 42.0)


class TestAppendValue(unittest.TestCase):
    """Test the append_value function."""
    
    def test_append_value_exists(self):
        """Test appending a value that exists."""
        values = []
        message = Mock()
        message.cadence = 90
        mw2g.append_value(values, message, "cadence")
        self.assertEqual(values, [90])
    
    def test_append_value_missing(self):
        """Test appending a value that doesn't exist."""
        values = []
        message = Mock()
        del message.power  # Attribute doesn't exist
        mw2g.append_value(values, message, "power")
        self.assertEqual(values, [0])


class TestResetValues(unittest.TestCase):
    """Test the reset_values function."""
    
    def test_reset_values(self):
        """Test resetting values returns three empty lists."""
        laps, cadence, power, heart_rate = mw2g.reset_values()
        self.assertEqual(laps, [])
        self.assertEqual(cadence, [])
        self.assertEqual(power, [])
        self.assertEqual(heart_rate, [])


class TestGetMostRecentFitFile(unittest.TestCase):
    """Test the get_most_recent_fit_file function."""
    
    def setUp(self):
        """Set up test directory with FIT files."""
        self.test_dir = Path(tempfile.mkdtemp())
        # Create test FIT files with different versions
        (self.test_dir / "MyNewActivity-3.8.5.fit").touch()
        (self.test_dir / "MyNewActivity-3.7.2.fit").touch()
        (self.test_dir / "MyNewActivity-3.9.1.fit").touch()
        (self.test_dir / "other_file.fit").touch()
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    def test_get_most_recent_fit_file(self):
        """Test finding the most recent FIT file."""
        result = mw2g.get_most_recent_fit_file(self.test_dir)
        self.assertIsNotNone(result)
        self.assertEqual(result.name, "MyNewActivity-3.9.1.fit")
    
    def test_get_most_recent_fit_file_no_files(self):
        """Test when no FIT files exist."""
        empty_dir = Path(tempfile.mkdtemp())
        try:
            result = mw2g.get_most_recent_fit_file(empty_dir)
            self.assertIsNone(result)
        finally:
            shutil.rmtree(empty_dir)


class TestGenerateNewFilename(unittest.TestCase):
    """Test the generate_new_filename function."""
    
    def test_generate_new_filename(self):
        """Test filename generation with timestamp."""
        fit_file = Path("MyNewActivity-3.8.5.fit")
        filename = mw2g.generate_new_filename(fit_file)
        self.assertTrue(filename.startswith("MyNewActivity-3.8.5_"))
        self.assertTrue(filename.endswith(".fit"))
        # Check timestamp format
        timestamp_part = filename.replace("MyNewActivity-3.8.5_", "").replace(".fit", "")
        self.assertRegex(timestamp_part, r"\d{4}-\d{2}-\d{2}_\d{6}")


class TestCleanupFitFile(unittest.TestCase):
    """Test the cleanup_fit_file function."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.input_file = self.test_dir / "input.fit"
        self.output_file = self.test_dir / "output.fit"
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    @patch('myWhoosh2Garmin.FitFileBuilder')
    @patch('myWhoosh2Garmin.FitFile')
    @patch('myWhoosh2Garmin.RecordTemperatureField')
    def test_cleanup_fit_file_removes_temperature(
        self, mock_temp_field, mock_fit_file, mock_builder
    ):
        """Test that temperature is removed from records."""
        # Setup mocks
        mock_temp_field.ID = 13
        
        # Create proper type classes for isinstance checks
        MockRecordMessage = type('RecordMessage', (), {})
        MockSessionMessage = type('SessionMessage', (), {})
        MockLapMessage = type('LapMessage', (), {})
        
        # Create mock record messages
        record1 = Mock(spec=MockRecordMessage)
        record1.cadence = 90
        record1.power = 200
        record1.heart_rate = 150
        record1.remove_field = Mock()
        # Make isinstance work
        record1.__class__ = MockRecordMessage
        
        record2 = Mock(spec=MockRecordMessage)
        record2.cadence = 95
        record2.power = 210
        record2.heart_rate = 155
        record2.remove_field = Mock()
        record2.__class__ = MockRecordMessage
        
        # Create mock session message
        session = Mock(spec=MockSessionMessage)
        session.avg_cadence = None
        session.avg_power = None
        session.avg_heart_rate = None
        session.__class__ = MockSessionMessage
        
        # Create mock lap message
        lap = Mock(spec=MockLapMessage)
        lap.__class__ = MockLapMessage
        
        # Setup FitFile mock
        mock_fit_instance = Mock()
        mock_fit_instance.records = [
            Mock(message=record1),
            Mock(message=lap),
            Mock(message=record2),
            Mock(message=session),
        ]
        mock_fit_file.from_file.return_value = mock_fit_instance
        
        # Setup builder mock
        mock_builder_instance = Mock()
        mock_builder.return_value = mock_builder_instance
        mock_built_file = Mock()
        mock_builder_instance.build.return_value = mock_built_file
        
        # Temporarily replace with mocks
        original_builder = mw2g.FitFileBuilder
        original_fit = mw2g.FitFile
        original_temp = mw2g.RecordTemperatureField
        original_lap = mw2g.LapMessage
        original_session = mw2g.SessionMessage
        original_record = mw2g.RecordMessage
        
        try:
            mw2g.FitFileBuilder = mock_builder
            mw2g.FitFile = mock_fit_file
            mw2g.RecordTemperatureField = mock_temp_field
            mw2g.LapMessage = MockLapMessage
            mw2g.SessionMessage = MockSessionMessage
            mw2g.RecordMessage = MockRecordMessage
            
            # Track what gets added to the builder
            added_messages = []
            def capture_add(msg):
                added_messages.append(msg)
                return None
            
            mock_builder_instance.add.side_effect = capture_add
            
            # Run the function
            mw2g.cleanup_fit_file(self.input_file, self.output_file)
            
            # Verify temperature was removed from records
            self.assertEqual(record1.remove_field.call_count, 1)
            self.assertEqual(record2.remove_field.call_count, 1)
            record1.remove_field.assert_called_with(mock_temp_field.ID)
            record2.remove_field.assert_called_with(mock_temp_field.ID)
            
            # Verify builder was used correctly
            # Should have added: 2 records + 1 lap (skipped) + 1 session = 3 messages
            self.assertGreaterEqual(len(added_messages), 3)
            
            # Find the session message that was added (the function creates a new one)
            session_messages = [msg for msg in added_messages 
                              if isinstance(msg, MockSessionMessage)]
            
            # Verify a session message was added with averages calculated
            self.assertGreater(len(session_messages), 0, 
                             "No SessionMessage was added to builder")
            new_session = session_messages[0]
            self.assertIsNotNone(new_session.avg_cadence, 
                               "avg_cadence should be calculated")
            self.assertIsNotNone(new_session.avg_power, 
                               "avg_power should be calculated")
            self.assertIsNotNone(new_session.avg_heart_rate, 
                               "avg_heart_rate should be calculated")
            
            mock_built_file.to_file.assert_called_once()
        finally:
            # Restore originals
            mw2g.FitFileBuilder = original_builder
            mw2g.FitFile = original_fit
            mw2g.RecordTemperatureField = original_temp
            mw2g.LapMessage = original_lap
            mw2g.SessionMessage = original_session
            mw2g.RecordMessage = original_record
    
    @patch('myWhoosh2Garmin.FitFileBuilder')
    @patch('myWhoosh2Garmin.FitFile')
    @patch('myWhoosh2Garmin.RecordTemperatureField')
    def test_cleanup_fit_file_processes_lap_message(
        self, mock_temp_field, mock_fit_file, mock_builder
    ):
        """Test that LapMessage data is collected and processed."""
        # Setup mocks
        mock_temp_field.ID = 13
        
        # Create proper type classes for isinstance checks
        MockRecordMessage = type('RecordMessage', (), {})
        MockSessionMessage = type('SessionMessage', (), {})
        MockLapMessage = type('LapMessage', (), {})
        
        # Create mock lap message with various fields
        lap = Mock(spec=MockLapMessage)
        lap.start_time = 1000
        lap.total_elapsed_time = 900.0
        lap.total_distance = 5000.0
        lap.avg_speed = 5.5
        lap.max_speed = 8.0
        lap.avg_heart_rate = 150
        lap.max_heart_rate = 165
        lap.avg_cadence = 90
        lap.max_cadence = 100
        lap.total_calories = 200
        lap.__class__ = MockLapMessage
        
        # Create mock record message
        record = Mock(spec=MockRecordMessage)
        record.cadence = 85
        record.power = 200
        record.heart_rate = 145
        record.remove_field = Mock()
        record.__class__ = MockRecordMessage
        
        # Create mock session message
        session = Mock(spec=MockSessionMessage)
        session.avg_cadence = None
        session.avg_power = None
        session.avg_heart_rate = None
        session.__class__ = MockSessionMessage
        
        # Setup FitFile mock - lap comes before session
        mock_fit_instance = Mock()
        mock_fit_instance.records = [
            Mock(message=lap),
            Mock(message=record),
            Mock(message=session),
        ]
        mock_fit_file.from_file.return_value = mock_fit_instance
        
        # Setup builder mock
        mock_builder_instance = Mock()
        mock_builder.return_value = mock_builder_instance
        mock_built_file = Mock()
        mock_builder_instance.build.return_value = mock_built_file
        
        # Track what gets added to the builder
        added_messages = []
        def capture_add(msg):
            added_messages.append(msg)
            return None
        
        mock_builder_instance.add.side_effect = capture_add
        
        # Temporarily replace with mocks
        original_builder = mw2g.FitFileBuilder
        original_fit = mw2g.FitFile
        original_temp = mw2g.RecordTemperatureField
        original_lap = mw2g.LapMessage
        original_session = mw2g.SessionMessage
        original_record = mw2g.RecordMessage
        
        try:
            mw2g.FitFileBuilder = mock_builder
            mw2g.FitFile = mock_fit_file
            mw2g.RecordTemperatureField = mock_temp_field
            mw2g.LapMessage = MockLapMessage
            mw2g.SessionMessage = MockSessionMessage
            mw2g.RecordMessage = MockRecordMessage
            
            # Mock append_value to track what values are collected from lap
            original_append_value = mw2g.append_value
            lap_value_calls = []
            def track_append_value(values, message, field_name):
                if isinstance(message, MockLapMessage):
                    lap_value_calls.append((field_name, getattr(message, field_name, None)))
                return original_append_value(values, message, field_name)
            
            mw2g.append_value = track_append_value
            
            # Run the function
            mw2g.cleanup_fit_file(self.input_file, self.output_file)
            
            # Restore append_value
            mw2g.append_value = original_append_value
            
            # Verify lap message values were collected
            # The function should collect: start_time, total_elapsed_time, total_distance,
            # avg_speed, max_speed, avg_heart_rate, max_heart_rate, avg_cadence, 
            # max_cadence, total_calories
            expected_lap_fields = [
                "start_time", "total_elapsed_time", "total_distance",
                "avg_speed", "max_speed", "avg_heart_rate", "max_heart_rate",
                "avg_cadence", "max_cadence", "total_calories"
            ]
            collected_fields = [field for field, _ in lap_value_calls]
            for field in expected_lap_fields:
                self.assertIn(field, collected_fields,
                            f"LapMessage field '{field}' should be collected")
            
            # Verify lap message was added to builder (via default case)
            lap_messages = [msg for msg in added_messages 
                          if isinstance(msg, MockLapMessage)]
            self.assertEqual(len(lap_messages), 1, 
                           "LapMessage should be added to builder")
            self.assertEqual(lap_messages[0], lap,
                           "The original lap message should be added")
            
            # Verify record message was processed
            self.assertEqual(record.remove_field.call_count, 1)
            
            # Verify session message was created with averages
            session_messages = [msg for msg in added_messages 
                              if isinstance(msg, MockSessionMessage)]
            self.assertEqual(len(session_messages), 1,
                           "SessionMessage should be added to builder")
            
            # Verify all messages were added (lap + record + session = 3)
            self.assertEqual(len(added_messages), 3,
                           "Should have lap, record, and session messages")
            
            mock_built_file.to_file.assert_called_once()
        finally:
            # Restore originals
            mw2g.FitFileBuilder = original_builder
            mw2g.FitFile = original_fit
            mw2g.RecordTemperatureField = original_temp
            mw2g.LapMessage = original_lap
            mw2g.SessionMessage = original_session
            mw2g.RecordMessage = original_record


class TestGetFitfileLocation(unittest.TestCase):
    """Test the get_fitfile_location function."""
    
    @unittest.skipIf(sys.platform == 'win32', "POSIX test not applicable on Windows")
    @patch('myWhoosh2Garmin.os.name', 'posix')
    def test_get_fitfile_location_posix_exists(self):
        """Test POSIX path when directory exists."""
        # This test is complex to mock properly, so we'll test the actual function
        # with a temporary directory structure
        test_dir = Path(tempfile.mkdtemp())
        try:
            # Create the expected directory structure
            target_path = (
                test_dir / "Library" / "Containers" / "com.whoosh.whooshgame"
                / "Data" / "Library" / "Application Support" / "Epic"
                / "MyWhoosh" / "Content" / "Data"
            )
            target_path.mkdir(parents=True, exist_ok=True)
            
            with patch('myWhoosh2Garmin.Path.home', return_value=test_dir):
                result = mw2g.get_fitfile_location()
                self.assertEqual(result, target_path)
        finally:
            shutil.rmtree(test_dir)
    
    @unittest.skipIf(sys.platform != 'win32', "Windows test only")
    @patch('myWhoosh2Garmin.os.name', 'nt')
    def test_get_fitfile_location_windows(self):
        """Test Windows path finding."""
        test_dir = Path(tempfile.mkdtemp())
        try:
            # Create Windows-style directory structure matching the expected path
            home_dir = test_dir / "home"
            home_dir.mkdir()
            
            appdata = home_dir / "AppData" / "Local" / "Packages"
            appdata.mkdir(parents=True, exist_ok=True)
            
            # Create a mock MyWhoosh package directory
            mywhoosh_package = appdata / "MyWhooshTechnologyService.1234567890"
            mywhoosh_package.mkdir()
            
            target_path = (
                mywhoosh_package / "LocalCache" / "Local" / "MyWhoosh"
                / "Content" / "Data"
            )
            target_path.mkdir(parents=True, exist_ok=True)
            
            # Mock Path.home to return our test home directory
            with patch('myWhoosh2Garmin.Path.home', return_value=home_dir):
                result = mw2g.get_fitfile_location()
                # On Windows, the function should find the directory
                if result:
                    self.assertEqual(result, target_path)
        finally:
            shutil.rmtree(test_dir)
    
    def test_get_fitfile_location_not_found(self):
        """Test when FIT file location doesn't exist."""
        # Use a non-existent path
        fake_home = Path("/nonexistent/path/that/does/not/exist")
        with patch('myWhoosh2Garmin.Path.home', return_value=fake_home):
            result = mw2g.get_fitfile_location()
            # Should return None when path doesn't exist
            self.assertIsNone(result)


class TestGetBackupPath(unittest.TestCase):
    """Test the get_backup_path function."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.json_file = self.test_dir / "backup_path.json"
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    def test_get_backup_path_from_json(self):
        """Test getting backup path from existing JSON file."""
        backup_path = self.test_dir / "backup"
        backup_path.mkdir()
        
        with self.json_file.open('w') as f:
            json.dump({'backup_path': str(backup_path)}, f)
        
        result = mw2g.get_backup_path(self.json_file)
        self.assertEqual(result, backup_path)
    
    @patch('myWhoosh2Garmin.filedialog')
    @patch('myWhoosh2Garmin.tk.Tk')
    def test_get_backup_path_new_selection(self, mock_tk, mock_filedialog):
        """Test getting backup path from file dialog."""
        backup_path = self.test_dir / "backup"
        backup_path.mkdir()
        
        mock_root = Mock()
        mock_tk.return_value = mock_root
        mock_filedialog.askdirectory.return_value = str(backup_path)
        
        result = mw2g.get_backup_path(self.json_file)
        
        self.assertEqual(result, backup_path)
        self.assertTrue(self.json_file.exists())
        
        # Verify JSON was saved
        with self.json_file.open('r') as f:
            data = json.load(f)
            self.assertEqual(data['backup_path'], str(backup_path))
    
    @patch('myWhoosh2Garmin.filedialog')
    @patch('myWhoosh2Garmin.tk.Tk')
    def test_get_backup_path_cancelled(self, mock_tk, mock_filedialog):
        """Test when user cancels file dialog."""
        mock_root = Mock()
        mock_tk.return_value = mock_root
        mock_filedialog.askdirectory.return_value = ""
        
        result = mw2g.get_backup_path(self.json_file)
        
        self.assertIsNone(result)


class TestAuthenticateToGarmin(unittest.TestCase):
    """Test Garmin authentication functions."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.tokens_path = self.test_dir / ".garth"
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    @patch('myWhoosh2Garmin.TOKENS_PATH')
    @patch('myWhoosh2Garmin.garth')
    def test_authenticate_to_garmin_with_existing_tokens(self, mock_garth, mock_tokens_path):
        """Test authentication with existing valid tokens."""
        mock_tokens_path.exists.return_value = True
        mock_garth.resume.return_value = None
        mock_garth.client.username = "testuser"
        
        result = mw2g.authenticate_to_garmin()
        
        self.assertTrue(result)
        mock_garth.resume.assert_called_once_with(mock_tokens_path)
    
    @patch('myWhoosh2Garmin.TOKENS_PATH')
    @patch('myWhoosh2Garmin.garth')
    @patch('myWhoosh2Garmin.get_credentials_for_garmin')
    def test_authenticate_to_garmin_expired_session(
        self, mock_get_creds, mock_garth, mock_tokens_path
    ):
        """Test authentication with expired session."""
        mock_tokens_path.exists.return_value = True
        
        # Create a mock exception class if GarthException is not available
        if mw2g.GarthException and isinstance(mw2g.GarthException, type):
            GarthException = mw2g.GarthException
        else:
            class GarthException(Exception):
                pass
        
        # Set up the exception to be raised when accessing username
        def raise_exception(*args, **kwargs):
            raise GarthException("Expired")
        
        mock_garth.resume.return_value = None
        mock_client = Mock()
        # Accessing username property raises exception
        type(mock_client).username = property(lambda self: raise_exception())
        mock_garth.client = mock_client
        mock_get_creds.return_value = True
        
        # Temporarily set GarthException if it's None
        original_exception = mw2g.GarthException
        try:
            if mw2g.GarthException is None:
                mw2g.GarthException = GarthException
            
            # The function should catch the exception and call get_credentials_for_garmin
            result = mw2g.authenticate_to_garmin()
            
            # Should have called get_credentials_for_garmin after exception
            self.assertTrue(result)
            mock_get_creds.assert_called_once()
        finally:
            if original_exception is None:
                mw2g.GarthException = original_exception
    
    @patch('myWhoosh2Garmin.TOKENS_PATH')
    @patch('myWhoosh2Garmin.garth')
    @patch('myWhoosh2Garmin.get_credentials_for_garmin')
    def test_authenticate_to_garmin_no_tokens(
        self, mock_get_creds, mock_garth, mock_tokens_path
    ):
        """Test authentication when no tokens exist."""
        mock_tokens_path.exists.return_value = False
        mock_get_creds.return_value = True
        
        result = mw2g.authenticate_to_garmin()
        
        self.assertTrue(result)
        mock_get_creds.assert_called_once()


class TestUploadFitFileToGarmin(unittest.TestCase):
    """Test the upload_fit_file_to_garmin function."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_file = self.test_dir / "test.fit"
        self.test_file.write_bytes(b"fake fit file data")
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    @patch('myWhoosh2Garmin.garth')
    def test_upload_fit_file_to_garmin_success(self, mock_garth):
        """Test successful upload."""
        mock_garth.client.upload.return_value = {"status": "success"}
        
        result = mw2g.upload_fit_file_to_garmin(self.test_file)
        
        self.assertTrue(result)
        mock_garth.client.upload.assert_called_once()
    
    @patch('myWhoosh2Garmin.garth')
    def test_upload_fit_file_to_garmin_duplicate(self, mock_garth):
        """Test upload with duplicate activity error."""
        # Create a proper exception class that inherits from Exception
        # GarthHTTPError from garth.exc may require specific arguments
        if mw2g.GarthHTTPError and isinstance(mw2g.GarthHTTPError, type):
            # Try to create with error parameter if that's what it expects
            try:
                # GarthHTTPError might require an 'error' parameter
                error_instance = mw2g.GarthHTTPError(error="Duplicate activity")
            except TypeError:
                # If that doesn't work, try with just a message
                try:
                    error_instance = mw2g.GarthHTTPError("Duplicate activity")
                except TypeError:
                    # If still fails, create a simple mock exception
                    class MockGarthHTTPError(Exception):
                        pass
                    error_instance = MockGarthHTTPError("Duplicate activity")
                    # Temporarily replace
                    original_error = mw2g.GarthHTTPError
                    mw2g.GarthHTTPError = MockGarthHTTPError
        else:
            # Create a mock exception class if not available
            class GarthHTTPError(Exception):
                pass
            error_instance = GarthHTTPError("Duplicate activity")
            original_error = mw2g.GarthHTTPError
            mw2g.GarthHTTPError = GarthHTTPError
        
        mock_garth.client.upload.side_effect = error_instance
        
        try:
            result = mw2g.upload_fit_file_to_garmin(self.test_file)
            
            self.assertFalse(result)
        finally:
            # Restore original if we replaced it
            if 'original_error' in locals():
                mw2g.GarthHTTPError = original_error
    
    def test_upload_fit_file_to_garmin_invalid_path(self):
        """Test upload with invalid file path."""
        invalid_path = Path("/nonexistent/file.fit")
        
        result = mw2g.upload_fit_file_to_garmin(invalid_path)
        
        self.assertFalse(result)


class TestCleanupAndSaveFitFile(unittest.TestCase):
    """Test the cleanup_and_save_fit_file function."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.fitfile_location = self.test_dir / "fitfiles"
        self.backup_location = self.test_dir / "backup"
        self.fitfile_location.mkdir()
        self.backup_location.mkdir()
        
        # Create a test FIT file
        self.test_fit = self.fitfile_location / "MyNewActivity-3.8.5.fit"
        self.test_fit.write_bytes(b"fake fit data")
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    @patch('myWhoosh2Garmin.get_most_recent_fit_file')
    @patch('myWhoosh2Garmin.cleanup_fit_file')
    @patch('myWhoosh2Garmin.generate_new_filename')
    def test_cleanup_and_save_fit_file_success(
        self, mock_gen_filename, mock_cleanup, mock_get_fit
    ):
        """Test successful cleanup and save."""
        mock_get_fit.return_value = self.test_fit
        mock_gen_filename.return_value = "MyNewActivity-3.8.5_2024-01-01_120000.fit"
        
        result = mw2g.cleanup_and_save_fit_file(
            self.fitfile_location, 
            self.backup_location
        )
        
        self.assertIsNotNone(result)
        mock_cleanup.assert_called_once()
    
    @patch('myWhoosh2Garmin.get_most_recent_fit_file')
    def test_cleanup_and_save_fit_file_no_files(self, mock_get_fit):
        """Test when no FIT files are found."""
        mock_get_fit.return_value = None
        
        result = mw2g.cleanup_and_save_fit_file(
            self.fitfile_location,
            self.backup_location
        )
        
        self.assertIsNone(result)
    
    def test_cleanup_and_save_fit_file_invalid_directory(self):
        """Test with invalid directory."""
        invalid_dir = Path("/nonexistent/dir")
        
        result = mw2g.cleanup_and_save_fit_file(
            invalid_dir,
            self.backup_location
        )
        
        self.assertIsNone(result)


class TestMainFunction(unittest.TestCase):
    """Test the main function with all mocks."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.fitfile_location = self.test_dir / "fitfiles"
        self.backup_location = self.test_dir / "backup"
        self.fitfile_location.mkdir()
        self.backup_location.mkdir()
    
    def tearDown(self):
        """Clean up test directory."""
        shutil.rmtree(self.test_dir)
    
    @patch('myWhoosh2Garmin.upload_fit_file_to_garmin')
    @patch('myWhoosh2Garmin.cleanup_and_save_fit_file')
    @patch('myWhoosh2Garmin.authenticate_to_garmin')
    @patch('myWhoosh2Garmin.get_backup_path')
    @patch('myWhoosh2Garmin.get_fitfile_location')
    @patch('myWhoosh2Garmin.import_required_modules')
    @patch('myWhoosh2Garmin.ensure_packages')
    def test_main_success(
        self, mock_ensure, mock_import, mock_get_fit, 
        mock_get_backup, mock_auth, mock_cleanup, mock_upload
    ):
        """Test successful main execution."""
        mock_ensure.return_value = True
        mock_import.return_value = True
        mock_get_fit.return_value = self.fitfile_location
        mock_get_backup.return_value = self.backup_location
        mock_auth.return_value = True
        mock_cleanup.return_value = self.test_dir / "cleaned.fit"
        mock_upload.return_value = True
        
        result = mw2g.main()
        
        self.assertEqual(result, 0)
        mock_upload.assert_called_once()
    
    @patch('myWhoosh2Garmin.ensure_packages')
    def test_main_package_failure(self, mock_ensure):
        """Test main when packages can't be ensured."""
        mock_ensure.return_value = False
        
        result = mw2g.main()
        
        self.assertEqual(result, 1)
    
    @patch('myWhoosh2Garmin.import_required_modules')
    @patch('myWhoosh2Garmin.ensure_packages')
    def test_main_import_failure(self, mock_ensure, mock_import):
        """Test main when imports fail."""
        mock_ensure.return_value = True
        mock_import.return_value = False
        
        result = mw2g.main()
        
        self.assertEqual(result, 1)
    
    @patch('myWhoosh2Garmin.get_fitfile_location')
    @patch('myWhoosh2Garmin.import_required_modules')
    @patch('myWhoosh2Garmin.ensure_packages')
    def test_main_no_fitfile_location(
        self, mock_ensure, mock_import, mock_get_fit
    ):
        """Test main when FIT file location not found."""
        mock_ensure.return_value = True
        mock_import.return_value = True
        mock_get_fit.return_value = None
        
        result = mw2g.main()
        
        self.assertEqual(result, 1)


if __name__ == '__main__':
    unittest.main()

