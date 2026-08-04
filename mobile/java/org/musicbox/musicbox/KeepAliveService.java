package org.musicbox.musicbox;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.media.session.MediaSession;
import android.os.Build;
import android.os.IBinder;
import android.os.PowerManager;

public class KeepAliveService extends Service {
    private static final int NOTIF_ID = 1;
    private static final String CHANNEL_ID = "musicbox_playback";

    public static final String ACTION_PLAY_PAUSE = "org.musicbox.musicbox.action.PLAY_PAUSE";
    public static final String ACTION_NEXT = "org.musicbox.musicbox.action.NEXT";
    public static final String ACTION_PREV = "org.musicbox.musicbox.action.PREV";
    public static final String ACTION_STOP = "org.musicbox.musicbox.action.STOP";
    private static final String EXTRA_TITLE = "title";
    private static final String EXTRA_COVER = "cover";
    private static final String EXTRA_PLAYING = "playing";

    private PowerManager.WakeLock wakeLock;
    private MediaSession mediaSession;
    private String currentTitle = "";
    private String currentCover = "";
    private boolean playing = true;

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        mediaSession = new MediaSession(this, "musicbox");
        mediaSession.setActive(true);
        startForegroundCompat();
        acquireWakeLock();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null) {
            if (intent.hasExtra(EXTRA_TITLE)) {
                currentTitle = intent.getStringExtra(EXTRA_TITLE);
            }
            if (intent.hasExtra(EXTRA_COVER)) {
                currentCover = intent.getStringExtra(EXTRA_COVER);
            }
            if (intent.hasExtra(EXTRA_PLAYING)) {
                playing = intent.getBooleanExtra(EXTRA_PLAYING, true);
            }
        }
        if (playing) {
            acquireWakeLock();
        } else {
            releaseWakeLock();
        }
        startForegroundCompat();
        return START_STICKY;
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        releaseWakeLock();
        stopForeground(true);
        stopSelf();
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        releaseWakeLock();
        if (mediaSession != null) {
            mediaSession.setActive(false);
            mediaSession.release();
        }
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }

    private void startForegroundCompat() {
        Notification n = buildNotification();
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK);
        } else {
            startForeground(NOTIF_ID, n);
        }
    }

    private void acquireWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            return;
        }
        try {
            PowerManager pm = (PowerManager) getSystemService(POWER_SERVICE);
            if (pm != null) {
                wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "musicbox:playback");
                wakeLock.setReferenceCounted(false);
                wakeLock.acquire();
            }
        } catch (Exception e) {
        }
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            try {
                wakeLock.release();
            } catch (Exception e) {
            }
        }
        wakeLock = null;
    }

    private void createChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                    CHANNEL_ID, "Odtwarzanie", NotificationManager.IMPORTANCE_LOW);
            NotificationManager nm = getSystemService(NotificationManager.class);
            if (nm != null) {
                nm.createNotificationChannel(channel);
            }
        }
    }

    private PendingIntent mediaAction(String action, int requestCode) {
        Intent intent = new Intent(action);
        intent.setPackage(getPackageName());
        return PendingIntent.getBroadcast(
                this, requestCode, intent,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }

    private Notification buildNotification() {
        Intent launch = new Intent(this, org.kivy.android.PythonActivity.class);
        launch.setFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(
                this, 0, launch,
                PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
        Notification.Builder builder;
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            builder = new Notification.Builder(this, CHANNEL_ID);
        } else {
            builder = new Notification.Builder(this);
        }
        int icon = getResources().getIdentifier("icon", "drawable", getPackageName());
        if (icon == 0) {
            icon = getApplicationInfo().icon;
        }
        String title = currentTitle != null && !currentTitle.isEmpty()
                ? currentTitle : "MusicBox";
        String text = playing ? "Odtwarzanie" : "Wstrzymano";
        int playPauseIcon = playing
                ? android.R.drawable.ic_media_pause : android.R.drawable.ic_media_play;
        String playPauseLabel = playing ? "Pauza" : "Odtwarzaj";
        builder
                .setSmallIcon(icon)
                .setContentTitle(title)
                .setContentText(text)
                .setContentIntent(pi)
                .setOngoing(true)
                .setCategory(Notification.CATEGORY_TRANSPORT)
                .addAction(android.R.drawable.ic_media_previous, "Poprzedni", mediaAction(ACTION_PREV, 1))
                .addAction(playPauseIcon, playPauseLabel, mediaAction(ACTION_PLAY_PAUSE, 2))
                .addAction(android.R.drawable.ic_media_next, "Następny", mediaAction(ACTION_NEXT, 3))
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Zatrzymaj", mediaAction(ACTION_STOP, 4));
        if (currentCover != null && !currentCover.isEmpty()) {
            Bitmap bmp = BitmapFactory.decodeFile(currentCover);
            if (bmp != null) {
                builder.setLargeIcon(bmp);
            }
        }
        if (mediaSession != null && Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            builder.setStyle(
                    new Notification.MediaStyle()
                            .setMediaSession(mediaSession.getSessionToken())
                            .setShowActionsInCompactView(0, 1, 2));
        }
        return builder.build();
    }
}
