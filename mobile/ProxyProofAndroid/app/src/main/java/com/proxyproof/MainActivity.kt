package com.proxyproof

import android.Manifest
import android.app.Activity
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothManager
import android.bluetooth.le.AdvertiseCallback
import android.bluetooth.le.AdvertiseData
import android.bluetooth.le.AdvertiseSettings
import android.bluetooth.le.BluetoothLeAdvertiser
import android.bluetooth.le.BluetoothLeScanner
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.ParcelUuid
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import java.util.UUID

class MainActivity : AppCompatActivity() {
    private val serviceUuid = ParcelUuid(UUID.fromString("1e8b7f40-8b7c-4e7b-9c52-9b22c0a7a101"))
    private lateinit var status: TextView
    private var advertiser: BluetoothLeAdvertiser? = null
    private var scanner: BluetoothLeScanner? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val manager = getSystemService(Context.BLUETOOTH_SERVICE) as BluetoothManager
        val adapter = manager.adapter
        advertiser = adapter?.bluetoothLeAdvertiser
        scanner = adapter?.bluetoothLeScanner

        val layout = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(40, 60, 40, 40)
            setBackgroundColor(android.graphics.Color.rgb(16, 23, 34))
        }
        status = TextView(this).apply {
            text = "ProxyProof BLE starter\n\nChoose a mode. Test on physical Android phones."
            textSize = 18f
            setTextColor(android.graphics.Color.WHITE)
        }
        val broadcast = Button(this).apply {
            text = "Organiser: Broadcast demo beacon"
            setOnClickListener { if (ensurePermissions()) startAdvertising() }
        }
        val scan = Button(this).apply {
            text = "Student: Scan for demo beacon"
            setOnClickListener { if (ensurePermissions()) startScanning() }
        }
        val stop = Button(this).apply {
            text = "Stop BLE"
            setOnClickListener { stopBle() }
        }
        layout.addView(status)
        layout.addView(broadcast)
        layout.addView(scan)
        layout.addView(stop)
        setContentView(layout)
    }

    private fun ensurePermissions(): Boolean {
        val required = if (Build.VERSION.SDK_INT >= 31) arrayOf(
            Manifest.permission.BLUETOOTH_SCAN,
            Manifest.permission.BLUETOOTH_ADVERTISE,
            Manifest.permission.BLUETOOTH_CONNECT
        ) else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)
        val missing = required.filter {
            ActivityCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 410)
            status.text = "Grant the requested Bluetooth permissions, then tap the button again."
            return false
        }
        return true
    }

    private fun startAdvertising() {
        val adv = advertiser
        if (adv == null) {
            status.text = "BLE advertising unavailable on this phone."
            return
        }
        try {
            val settings = AdvertiseSettings.Builder()
                .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_LOW_LATENCY)
                .setConnectable(false)
                .setTimeout(0)
                .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_LOW)
                .build()
            // Demo-only fixed marker. Production must broadcast compact rotating authenticated data.
            val data = AdvertiseData.Builder().addServiceUuid(serviceUuid).build()
            adv.startAdvertising(settings, data, object : AdvertiseCallback() {
                override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
                    runOnUiThread { status.text = "Organiser beacon is broadcasting (demo marker only)." }
                }
                override fun onStartFailure(errorCode: Int) {
                    runOnUiThread { status.text = "Advertising failed: $errorCode. Phone may not support advertising." }
                }
            })
        } catch (e: SecurityException) {
            status.text = "Bluetooth permission missing: ${e.message}"
        }
    }

    private fun startScanning() {
        val scanApi = scanner
        if (scanApi == null) {
            status.text = "BLE scanner unavailable on this phone."
            return
        }
        try {
            val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
            scanApi.startScan(null, settings, object : ScanCallback() {
                override fun onScanResult(callbackType: Int, result: ScanResult) {
                    if (result.scanRecord?.serviceUuids?.contains(serviceUuid) == true) {
                        runOnUiThread {
                            status.text = "ProxyProof demo beacon found. RSSI: ${result.rssi} dBm\nThis sample does not mark server attendance yet."
                        }
                    }
                }
                override fun onScanFailed(errorCode: Int) {
                    runOnUiThread { status.text = "Scan failed: $errorCode" }
                }
            })
            status.text = "Scanning for ProxyProof demo beacons..."
        } catch (e: SecurityException) {
            status.text = "Bluetooth permission missing: ${e.message}"
        }
    }

    private fun stopBle() {
        try {
            advertiser?.stopAdvertising(advertiseCallbackNoop)
        } catch (_: Exception) {}
        try {
            scanner?.stopScan(scanCallbackNoop)
        } catch (_: Exception) {}
        status.text = "Stop requested. Android may report a harmless warning if no scan was active."
    }

    private val advertiseCallbackNoop = object : AdvertiseCallback() {}
    private val scanCallbackNoop = object : ScanCallback() {}
}
