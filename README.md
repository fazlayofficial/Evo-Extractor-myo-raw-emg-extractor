# Evo_Extractor: Raw EMG Data Acquisition Framework for Myo Armband

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/Status-Research_Prototype-orange.svg)]()
[![IEEE](https://img.shields.io/badge/IEEE-ICEEIE_2025-green.svg)](https://doi.org/10.1109/ICEEIE66203.2025.11252161)

**Authors:** Fazlay Rabby, Md. Rifat Aknda  
**Institution:** Evomed Technology  

---

## Abstract

Evo_Extractor is a research-grade software framework designed to facilitate high-fidelity electromyography (EMG) signal acquisition from the Myo Armband via Bluetooth Low Energy (BLE) protocol. This tool bypasses the manufacturer's preprocessing pipeline to provide direct access to raw analog-to-digital converter (ADC) outputs, enabling researchers to perform custom signal processing and feature extraction without proprietary filtering artifacts.

The framework supports real-time data visualization, structured data logging in CSV format, and includes an experimental keyboard mapping interface for human-computer interaction (HCI) applications. This implementation was developed to support our work on scalable gesture recognition using hybrid deep learning architectures.

---

## Technical Specifications

### Signal Acquisition
- **Data Source:** Myo Armband (8-channel dry electrode system)
- **ADC Resolution:** 8-bit signed integer (-128 to 127)
- **Sampling Frequency:** 200 Hz per channel
- **Communication Protocol:** Bluetooth Low Energy (BLE) 4.0+
- **Data Format:** Unfiltered, unprocessed ADC values

### Software Architecture
- **Language:** Python 3.11+
- **Core Dependencies:** `bleak` (BLE communication), `numpy` (signal processing), `matplotlib` (visualization)
- **Deployment:** Standalone executable via PyInstaller for Windows x64

---

## Key Features

### 1. Direct ADC Access
Unlike consumer-facing applications that apply proprietary smoothing and filtering, Evo_Extractor extracts raw 8-bit signed integer values directly from the device's analog-to-digital converter. This ensures that researchers have complete control over preprocessing pipelines and can implement custom filtering strategies appropriate to their experimental paradigm.

### 2. High-Frequency Data Logging
The system maintains a stable 200 Hz sampling rate across all eight channels, with timestamps synchronized to system clock. Data is automatically exported to CSV files with user-defined profile metadata, facilitating batch processing in MATLAB, Python (NumPy/Pandas), or R.

### 3. Real-Time Visualization
Multi-channel time-series visualization using Matplotlib enables immediate verification of signal quality, electrode contact, and motion artifacts during data collection sessions.

### 4. Profile-Based Data Management
The framework implements a session management system allowing researchers to organize data collection by participant, experimental condition, or gesture class. Each profile generates separate CSV files with consistent formatting for downstream analysis.

### 5. Experimental HCI Module
An optional keyboard mapping subsystem translates EMG activity into discrete keyboard events, enabling preliminary testing of control paradigms for assistive technologies or prosthetic interfaces.

---

## Installation

### Prerequisites
- Python 3.11 or later
- Windows 10/11 (64-bit) for executable deployment
- Myo Armband with compatible Bluetooth 4.0+ adapter
- Development: Visual Studio Code (recommended)

### Option A: Binary Distribution (Recommended for End Users)

1. Navigate to the [Releases](../../releases) page
2. Download `Evo_Extractor_v1.0_Win64.zip`
3. Extract archive and execute `Evo_Extractor.exe`
4. No Python installation or dependency management required

### Option B: Source Installation (For Developers)

#### Automated Setup
```bash
git clone https://github.com/fazlayofficial/Evo-Extractor-Myo-EMG.git
cd Evo-Extractor-Myo-EMG
setup_env.bat
python app.py
```

#### Manual Configuration
```powershell
# Create isolated Python environment
python -m venv .venv

# Configure execution policy (Windows only)
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Activate virtual environment
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Launch application
python app.py
```

---

## Data Structure

### CSV Output Format

| Column | Data Type | Range | Description |
|--------|-----------|-------|-------------|
| Timestamp | float64 | N/A | Unix epoch time (seconds) |
| Channel_1 | int8 | [-128, 127] | EMG sensor pod 1 (proximal) |
| Channel_2 | int8 | [-128, 127] | EMG sensor pod 2 |
| ... | ... | ... | ... |
| Channel_8 | int8 | [-128, 127] | EMG sensor pod 8 (distal) |
| Label | string | N/A | User-defined gesture class or key event |

**Important Notes:**
- Values represent raw ADC output with no normalization
- No bandpass filtering, notch filtering, or rectification applied
- Researchers should implement appropriate preprocessing based on experimental requirements

---

## Research Applications

This framework is designed to support research in:

1. **Biomedical Signal Processing:** Development and validation of novel EMG processing algorithms
2. **Pattern Recognition:** Training datasets for supervised learning of gesture classification models
3. **Human-Computer Interaction:** Prototyping EMG-based control interfaces
4. **Assistive Technology:** Data collection for prosthetic control systems or wheelchair interfaces
5. **Neuromuscular Research:** Analysis of muscle activation patterns and motor unit recruitment

---

## Building from Source

To compile the standalone Windows executable:

```bash
build_exe.bat
```

The executable will be generated in the `dist/` directory. The build script automatically bundles required assets (`logo.png`, `powered_by.png`) and Python dependencies.

---

## Citation

This software was developed to support our research on scalable hand gesture recognition using hybrid deep learning models. If you use this tool in your research, please cite:

### IEEE Citation Format
F. Rabby, R. Das, Md. M. Rahman, Md. H. Hossain, and Md. R. Aknda, "Scalable Hand Gesture Recognition from Surface Electromyography (sEMG) Signals Using a Hybrid Deep Learning Model Evaluated on Diverse Datasets," in *Proc. IEEE Int. Conf. Electrical, Electronics and Information Engineering (ICEEIE)*, Sep. 2025, doi: 10.1109/ICEEIE66203.2025.11252161.

### BibTeX
```bibtex
@inproceedings{rabby2025scalable,
  title={Scalable Hand Gesture Recognition from Surface Electromyography (sEMG) Signals Using a Hybrid Deep Learning Model Evaluated on Diverse Datasets},
  author={Rabby, Fazlay and Das, Rajdeep and Rahman, Md. Musfiqur and Hossain, Md. Hridoy and Aknda, Md. Rifat},
  booktitle={2025 IEEE International Conference on Electrical, Electronics and Information Engineering (ICEEIE)},
  year={2025},
  month={Sep.},
  publisher={IEEE},
  doi={10.1109/ICEEIE66203.2025.11252161}
}
```

---

## Contributors

- **Fazlay Rabby** – Primary Developer, System Architecture | [GitHub](https://github.com/fazlayofficial)
- **Md. Rifat Aknda** – Co-Developer, Signal Processing Module

---

## License & Distribution

This software is released as open-source research code. Users are free to modify and redistribute the code with appropriate attribution. For commercial applications or licensing inquiries, please contact the authors.

---

## Support & Contribution

We welcome contributions from the research community. To report issues or suggest enhancements:

1. Open an issue in the [GitHub Issue Tracker](../../issues)
2. Submit pull requests with detailed descriptions of changes
3. For research collaborations, contact via institutional email

---

**Powered by Evomed Technology**  
*Advancing biomedical signal processing research*