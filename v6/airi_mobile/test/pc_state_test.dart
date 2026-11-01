import 'dart:convert';

import 'package:airi_mobile/models/pc_state.dart';
import 'package:flutter_test/flutter_test.dart';

/// Exact payload the Axum backend returns when it cannot measure memory:
/// `data_source: "unavailable"` with every reading null.
const Map<String, dynamic> _memoryUnavailable = {
  'status': 'ok',
  'data_source': 'unavailable',
  'detail': 'memory telemetry not sampled on this host',
  'total': null,
  'used': null,
  'available': null,
  'usage_percent': null,
  'server': 'ARIA-Axum-8002',
};

const Map<String, dynamic> _volumeUnavailable = {
  'status': 'ok',
  'data_source': 'unavailable',
  'detail': 'volume telemetry not sampled on this host',
  'volume': null,
  'muted': null,
  'server': 'ARIA-Axum-8002',
};

void main() {
  group('MemoryInfo', () {
    test('data_source unavailable keeps every reading null', () {
      final memory = MemoryInfo.fromJson(_memoryUnavailable);

      expect(memory.measured, isFalse);
      expect(memory.total, isNull);
      expect(memory.used, isNull);
      expect(memory.available, isNull);
      expect(memory.usagePercent, isNull);
      expect(memory.dataSource, 'unavailable');
    });

    test('unavailable renders the non-numeric placeholder', () {
      final memory = MemoryInfo.fromJson(_memoryUnavailable);

      expect(memory.totalLabel, '—');
      expect(memory.usedLabel, '—');
      expect(memory.availableLabel, '—');
      expect(memory.usagePercentLabel, '—');
      expect(memory.usageFraction, isNull);
    });

    test('a null total is unmeasured even without data_source', () {
      final memory = MemoryInfo.fromJson({'total': null, 'used': null});

      expect(memory.measured, isFalse);
      expect(memory.used, isNull);
      expect(memory.usagePercent, isNull);
      expect(memory.usagePercentLabel, '—');
    });

    test('a measured zero is not the placeholder', () {
      final memory = MemoryInfo.fromJson({
        'data_source': 'ok',
        'total': 1024,
        'used': 0,
        'available': 1024,
      });

      expect(memory.measured, isTrue);
      expect(memory.used, 0);
      expect(memory.usedLabel, '0 B');
      expect(memory.totalLabel, '1.0 KB');
      expect(memory.availableLabel, '1.0 KB');
      expect(memory.usagePercent, 0.0);
      expect(memory.usagePercentLabel, '0%');
      expect(memory.usageFraction, 0.0);
    });

    test('derives available and usage_percent when the backend omits them', () {
      final memory = MemoryInfo.fromJson({'total': 1000, 'used': 250});

      expect(memory.measured, isTrue);
      expect(memory.available, 750);
      expect(memory.usagePercent, 25.0);
      expect(memory.usagePercentLabel, '25%');
      expect(memory.usageFraction, 0.25);
    });

    test('an explicit usage_percent wins over the derived one', () {
      final memory = MemoryInfo.fromJson({
        'total': 1000,
        'used': 500,
        'usage_percent': 42.0,
      });

      expect(memory.usagePercent, 42.0);
      expect(memory.usagePercentLabel, '42%');
      // The derived value is not used anywhere, but available still is.
      expect(memory.available, 500);
    });

    test('an undefined ratio stays null instead of becoming NaN or 0', () {
      final memory = MemoryInfo.fromJson({'total': 0, 'used': 0});

      expect(memory.measured, isTrue);
      expect(memory.totalLabel, '0 B');
      expect(memory.usagePercent, isNull);
      expect(memory.usagePercentLabel, '—');
      expect(memory.usageFraction, isNull);
    });
  });

  group('VolumeInfo', () {
    test('data_source unavailable keeps volume and muted null', () {
      final volume = VolumeInfo.fromJson(_volumeUnavailable);

      expect(volume.measured, isFalse);
      expect(volume.volume, isNull);
      expect(volume.muted, isNull);
      expect(volume.dataSource, 'unavailable');
    });

    test('unavailable renders the placeholder and no mute state', () {
      final volume = VolumeInfo.fromJson(_volumeUnavailable);

      expect(volume.volumeLabel, '—');
      expect(volume.mutedLabel, isNull);
    });

    test('a null volume is unmeasured and never becomes 75', () {
      final volume = VolumeInfo.fromJson({'volume': null, 'muted': false});

      expect(volume.measured, isFalse);
      expect(volume.volume, isNull);
      expect(volume.volumeLabel, '—');
      expect(volume.mutedLabel, isNull);
    });

    test('a measured level keeps its real value, including zero', () {
      final volume = VolumeInfo.fromJson({
        'data_source': 'ok',
        'volume': 0,
        'muted': false,
      });

      expect(volume.measured, isTrue);
      expect(volume.volume, 0);
      expect(volume.volumeLabel, '0');
      expect(volume.muted, isFalse);
      expect(volume.mutedLabel, 'activo');
    });

    test('a measured level keeps its real value and mute state', () {
      final volume = VolumeInfo.fromJson({
        'data_source': 'ok',
        'volume': 75,
        'muted': true,
      });

      expect(volume.volume, 75);
      expect(volume.volumeLabel, '75');
      expect(volume.muted, isTrue);
      expect(volume.mutedLabel, 'silenciado');
    });
  });

  group('PcStateSnapshot round-trip', () {
    test('preserves unmeasured memory and volume as nulls', () {
      final snapshot = PcStateSnapshot(
        memory: MemoryInfo.fromJson(_memoryUnavailable),
        volume: VolumeInfo.fromJson(_volumeUnavailable),
      );

      final decoded = jsonDecode(snapshot.encode()) as Map<String, dynamic>;
      final restored = PcStateSnapshot.fromJson(decoded);

      expect(restored.memory, isNotNull);
      expect(restored.memory!.total, isNull);
      expect(restored.memory!.used, isNull);
      expect(restored.memory!.available, isNull);
      expect(restored.memory!.usagePercent, isNull);
      expect(restored.memory!.measured, isFalse);
      expect(restored.memory!.totalLabel, '—');

      expect(restored.volume, isNotNull);
      expect(restored.volume!.volume, isNull);
      expect(restored.volume!.muted, isNull);
      expect(restored.volume!.measured, isFalse);
      expect(restored.volume!.volumeLabel, '—');
    });

    test('preserves measured values unchanged', () {
      final snapshot = PcStateSnapshot(
        memory: MemoryInfo.fromJson({'total': 2048, 'used': 512}),
        volume: VolumeInfo.fromJson({'volume': 40, 'muted': true}),
      );

      final decoded = jsonDecode(snapshot.encode()) as Map<String, dynamic>;
      final restored = PcStateSnapshot.fromJson(decoded);

      expect(restored.memory!.measured, isTrue);
      expect(restored.memory!.total, 2048);
      expect(restored.memory!.available, 1536);
      expect(restored.memory!.usagePercent, 25.0);
      expect(restored.volume!.measured, isTrue);
      expect(restored.volume!.volume, 40);
      expect(restored.volume!.muted, isTrue);
    });
  });
}
