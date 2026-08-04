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
import android.media.AudioAttributes;
import android.media.AudioManager;
import android.media.MediaPlayer;
import android.media.session.MediaSession;
import android.os.Build;
import android.os.Handler;
import android.os.IBinder;
import android.os.PowerManager;

public class KeepAliveService extends Service {
    private static final int NOTIF_ID = 1;
    private static final String CHANNEL_ID = "musicbox_playback";

    public static final String ACTION_PLAY_PAUSE = "org.musicbox.musicbox.action.PLAY_PAUSE";
    public static final String ACTION_NEXT = "org.musicbox.musicbox.action.NEXT";
    public static final String ACTION_PREV = "org.musicbox.musicbox.action.PREV";
    public static final String ACTION_STOP = "org.musicbox.musicbox.action.STOP";

    public static final String CMD_PLAY = "org.musicbox.musicbox.cmd.PLAY";
    public static final String CMD_PAUSE = "org.musicbox.musicbox.cmd.PAUSE";
    public static final String CMD_RESUME = "org.musicbox.musicbox.cmd.RESUME";
    public static final String CMD_NEXT = "org.musicbox.musicbox.cmd.NEXT";
    public static final String CMD_PREV = "org.musicbox.musicbox.cmd.PREV";
    public static final String CMD_STOP = "org.musicbox.musicbox.cmd.STOP";
    public static final String CMD_SEEK = "org.musicbox.musicbox.cmd.SEEK";
    public static final String CMD_REPEAT = "org.musicbox.musicbox.cmd.REPEAT";
    public static final String CMD_META = "org.musicbox.musicbox.cmd.META";
    public static final String CMD_ORDER = "org.musicbox.musicbox.cmd.ORDER";

    public static final String ACTION_STATE = "org.musicbox.musicbox.state.CHANGED";
    public static final String ACTION_POSITION = "org.musicbox.musicbox.state.POSITION";

    private static final String EXTRA_PATH = "path";
    private static final String EXTRA_PATHS = "paths";
    private static final String EXTRA_INDEX = "index";
    private static final String EXTRA_REPEAT = "repeat";
    private static final String EXTRA_TITLE = "title";
    private static final String EXTRA_COVER = "cover";
    private static final String EXTRA_PLAYING = "playing";
    private static final String EXTRA_ENDED = "ended";
    private static final String EXTRA_POSITION_MS = "position_ms";
    private static final String EXTRA_DURATION_MS = "duration_ms";
    private static final String EXTRA_RESUME_MS = "resume_ms";
    private static final String EXTRA_TITLES = "titles";
    private static final String EXTRA_COVERS = "covers";
    private static final String EXTRA_HAS_COVERS = "has_covers";

    private static final int REPEAT_OFF = 0;
    private static final int REPEAT_ALL = 1;
    private static final int REPEAT_ONE = 2;

    private PowerManager.WakeLock wakeLock;
    private MediaSession mediaSession;
    private MediaPlayer mediaPlayer;
    private Handler handler = new Handler();
    private String[] paths;
    private String[] metaTitles;
    private String[] metaCovers;
    private int index = -1;
    private boolean playing = false;
    private int repeatMode = REPEAT_ALL;
    private String currentTitle = "";
    private String currentCover = "";

    private final Runnable positionRunnable = new Runnable() {
        @Override
        public void run() {
            if (mediaPlayer != null && playing) {
                try {
                    int pos = mediaPlayer.getCurrentPosition();
                    int dur = mediaPlayer.getDuration();
                    sendPosition(pos, dur);
                } catch (Exception e) {
                }
                handler.postDelayed(this, 500);
            }
        }
    };

    @Override
    public void onCreate() {
        super.onCreate();
        createChannel();
        mediaSession = new MediaSession(this, "musicbox");
        mediaSession.setActive(true);
        startForegroundCompat();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        startForegroundCompat();
        if (intent != null && intent.getAction() != null) {
            handleAction(intent.getAction(), intent);
        }
        return START_STICKY;
    }

    private void handleAction(String action, Intent intent) {
        if (CMD_PLAY.equals(action)) {
            paths = splitPaths(intent.getStringExtra(EXTRA_PATHS));
            index = parseInt(intent.getStringExtra(EXTRA_INDEX), 0);
            repeatMode = parseInt(intent.getStringExtra(EXTRA_REPEAT), REPEAT_ALL);
            currentTitle = intent.getStringExtra(EXTRA_TITLE) == null
                    ? "" : intent.getStringExtra(EXTRA_TITLE);
            currentCover = intent.getStringExtra(EXTRA_COVER) == null
                    ? "" : intent.getStringExtra(EXTRA_COVER);
            int resumeMs = parseInt(intent.getStringExtra(EXTRA_RESUME_MS), 0);
            playTrack(index, resumeMs);
        } else if (CMD_PAUSE.equals(action) || ACTION_PLAY_PAUSE.equals(action) && playing) {
            pausePlayer();
        } else if (CMD_RESUME.equals(action) || ACTION_PLAY_PAUSE.equals(action) && !playing) {
            resumePlayer();
        } else if (CMD_NEXT.equals(action) || ACTION_NEXT.equals(action)) {
            step(1);
        } else if (CMD_PREV.equals(action) || ACTION_PREV.equals(action)) {
            step(-1);
        } else if (CMD_STOP.equals(action) || ACTION_STOP.equals(action)) {
            stopPlayback();
        } else if (CMD_SEEK.equals(action)) {
            if (mediaPlayer != null) {
                try {
                    mediaPlayer.seekTo(parseInt(intent.getStringExtra(EXTRA_POSITION_MS), 0));
                } catch (Exception e) {
                }
            }
        } else if (CMD_REPEAT.equals(action)) {
            repeatMode = parseInt(intent.getStringExtra(EXTRA_REPEAT), repeatMode);
        } else if (CMD_META.equals(action)) {
            metaTitles = splitPaths(intent.getStringExtra(EXTRA_TITLES));
            if ("1".equals(intent.getStringExtra(EXTRA_HAS_COVERS))) {
                metaCovers = splitPaths(intent.getStringExtra(EXTRA_COVERS));
            }
            if (index >= 0) {
                updateMetaForIndex(index);
                updateNotification();
            }
        } else if (CMD_ORDER.equals(action)) {
            String[] newPaths = splitPaths(intent.getStringExtra(EXTRA_PATHS));
            if (newPaths.length == 0) {
                return;
            }
            String current = (paths != null && index >= 0 && index < paths.length)
                    ? paths[index] : "";
            paths = newPaths;
            metaTitles = splitPaths(intent.getStringExtra(EXTRA_TITLES));
            if ("1".equals(intent.getStringExtra(EXTRA_HAS_COVERS))) {
                metaCovers = splitPaths(intent.getStringExtra(EXTRA_COVERS));
            }
            index = -1;
            if (!current.isEmpty()) {
                for (int i = 0; i < paths.length; i++) {
                    if (current.equals(paths[i])) {
                        index = i;
                        break;
                    }
                }
            }
            updateMetaForIndex(index);
            sendState(false);
            updateNotification();
        }
    }

    private void updateMetaForIndex(int idx) {
        if (metaTitles != null && idx >= 0 && idx < metaTitles.length
                && metaTitles[idx] != null && !metaTitles[idx].isEmpty()) {
            currentTitle = metaTitles[idx];
        }
        if (metaCovers != null && idx >= 0 && idx < metaCovers.length
                && metaCovers[idx] != null && !metaCovers[idx].isEmpty()) {
            currentCover = metaCovers[idx];
        }
    }

    private int parseInt(String s, int def) {
        if (s == null) {
            return def;
        }
        try {
            return Integer.parseInt(s);
        } catch (Exception e) {
            return def;
        }
    }

    private String[] splitPaths(String joined) {
        if (joined == null || joined.isEmpty()) {
            return new String[0];
        }
        return joined.split("\\n");
    }

    private void playTrack(int newIndex, int resumeMs) {
        if (paths == null || paths.length == 0 || newIndex < 0 || newIndex >= paths.length) {
            stopPlayback();
            return;
        }
        index = newIndex;
        updateMetaForIndex(index);
        try {
            if (mediaPlayer != null) {
                try {
                    mediaPlayer.release();
                } catch (Exception e) {
                }
            }
            mediaPlayer = new MediaPlayer();
            mediaPlayer.setAudioAttributes(new AudioAttributes.Builder()
                    .setLegacyStreamType(AudioManager.STREAM_MUSIC).build());
            mediaPlayer.setDataSource(paths[index]);
            mediaPlayer.prepare();
            mediaPlayer.setOnCompletionListener(new MediaPlayer.OnCompletionListener() {
                @Override
                public void onCompletion(MediaPlayer mp) {
                    onTrackCompleted();
                }
            });
            if (resumeMs > 0) {
                mediaPlayer.seekTo(resumeMs);
                mediaPlayer.start();
                mediaPlayer.pause();
                playing = false;
            } else {
                mediaPlayer.start();
                playing = true;
            }
            acquireWakeLock();
            handler.removeCallbacks(positionRunnable);
            handler.post(positionRunnable);
            sendState(false);
            updateNotification();
        } catch (Exception e) {
            playing = false;
            releasePlayer();
            sendState(true);
        }
    }

    private void onTrackCompleted() {
        if (repeatMode == REPEAT_ONE) {
            try {
                mediaPlayer.seekTo(0);
                mediaPlayer.start();
                playing = true;
                sendState(false);
                return;
            } catch (Exception e) {
            }
        }
        if (index + 1 >= paths.length) {
            if (repeatMode == REPEAT_OFF) {
                stopPlayback();
                return;
            }
            index = 0;
        } else {
            index += 1;
        }
        playTrack(index, 0);
    }

    private void step(int delta) {
        if (paths == null || paths.length == 0) {
            return;
        }
        int target = index + delta;
        if (target < 0) {
            target = paths.length - 1;
        } else if (target >= paths.length) {
            target = 0;
        }
        playTrack(target, 0);
    }

    private void pausePlayer() {
        playing = false;
        if (mediaPlayer != null) {
            try {
                mediaPlayer.pause();
            } catch (Exception e) {
            }
        }
        releaseWakeLock();
        handler.removeCallbacks(positionRunnable);
        updateNotification();
        sendState(false);
    }

    private void resumePlayer() {
        if (mediaPlayer == null) {
            if (paths != null && paths.length > 0 && index >= 0 && index < paths.length) {
                playTrack(index, 0);
            }
            return;
        }
        try {
            mediaPlayer.start();
            playing = true;
            acquireWakeLock();
            handler.removeCallbacks(positionRunnable);
            handler.post(positionRunnable);
            updateNotification();
            sendState(false);
        } catch (Exception e) {
        }
    }

    private void stopPlayback() {
        playing = false;
        releasePlayer();
        releaseWakeLock();
        handler.removeCallbacks(positionRunnable);
        sendState(true);
        stopForeground(true);
        stopSelf();
    }

    private void releasePlayer() {
        if (mediaPlayer != null) {
            try {
                mediaPlayer.release();
            } catch (Exception e) {
            }
        }
        mediaPlayer = null;
    }

    private void sendState(boolean ended) {
        Intent i = new Intent(ACTION_STATE).setPackage(getPackageName());
        i.putExtra(EXTRA_PATH, paths != null && index >= 0 && index < paths.length
                ? paths[index] : "");
        i.putExtra(EXTRA_INDEX, index);
        i.putExtra(EXTRA_PLAYING, playing);
        i.putExtra(EXTRA_ENDED, ended);
        i.putExtra(EXTRA_TITLE, currentTitle);
        i.putExtra(EXTRA_COVER, currentCover);
        sendBroadcast(i);
    }

    private void sendPosition(int pos, int dur) {
        Intent i = new Intent(ACTION_POSITION).setPackage(getPackageName());
        i.putExtra(EXTRA_POSITION_MS, pos);
        i.putExtra(EXTRA_DURATION_MS, dur);
        i.putExtra(EXTRA_PLAYING, playing);
        sendBroadcast(i);
    }

    @Override
    public void onTaskRemoved(Intent rootIntent) {
        releaseWakeLock();
        handler.removeCallbacks(positionRunnable);
        releasePlayer();
        stopForeground(true);
        stopSelf();
        super.onTaskRemoved(rootIntent);
    }

    @Override
    public void onDestroy() {
        releaseWakeLock();
        handler.removeCallbacks(positionRunnable);
        releasePlayer();
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

    private PendingIntent serviceAction(String action, int requestCode) {
        Intent intent = new Intent(this, KeepAliveService.class);
        intent.setAction(action);
        intent.setPackage(getPackageName());
        return PendingIntent.getService(
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
                .addAction(android.R.drawable.ic_media_previous, "Poprzedni", serviceAction(ACTION_PREV, 1))
                .addAction(playPauseIcon, playPauseLabel, serviceAction(ACTION_PLAY_PAUSE, 2))
                .addAction(android.R.drawable.ic_media_next, "Następny", serviceAction(ACTION_NEXT, 3))
                .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Zatrzymaj", serviceAction(ACTION_STOP, 4));
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

    private void updateNotification() {
        NotificationManager nm = (NotificationManager) getSystemService(NOTIFICATION_SERVICE);
        if (nm != null) {
            nm.notify(NOTIF_ID, buildNotification());
        }
    }
}
