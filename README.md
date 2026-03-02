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
Unlike consumer-facing applications that apply proprietary smoothing and filtering, Evo_Extractor extracts raw 8-bit signed integer values directly from the device's analog-to-digital converter.

### 2. High-Frequency Data Logging
The system maintains a stable 200 Hz sampling rate across all eight channels, with timestamps synchronized to the system clock. Data is exported to CSV for batch processing in MATLAB, Python, or R.

### 3. Real-Time Visualization
Multi-channel time-series visualization enables immediate verification of signal quality and electrode contact during data collection.

---

## Citation

If you use this software or the associated research in your work, please cite it as follows:

### IEEE Format
F. Rabby, R. Das, Md. M. Rahman, Md. H. Hossain, and Md. R. Aknda, "Scalable Hand Gesture Recognition from Surface Electromyography (sEMG) Signals Using a Hybrid Deep Learning Model Evaluated on Diverse Datasets," in *Proc. 2025 9th International Conference On Electrical, Electronics And Information Engineering (ICEEIE)*, Sep. 2025, pp. 1-6, doi: 10.1109/ICEEIE66203.2025.11252161.

### BibTeX
```bibtex
@INPROCEEDINGS{11252161,
  author={Rabby, Fazlay and Das, Rajdeep and Rahman, Md. Musfiqur and Hossain, Md. Hridoy and Aknda, Md. Rifat},
  booktitle={2025 9th International Conference On Electrical, Electronics And Information Engineering (ICEEIE)}, 
  title={Scalable Hand Gesture Recognition from Surface Electromyography (sEMG) Signals Using a Hybrid Deep Learning Model Evaluated on Diverse Datasets}, 
  year={2025},
  volume={},
  number={},
  pages={1-6},
  doi={10.1109/ICEEIE66203.2025.11252161},
  month={Sep.},
}