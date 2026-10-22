package org.peacock.shell;

import android.app.Activity;
import android.graphics.Typeface;
import android.os.Bundle;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import java.nio.charset.StandardCharsets;

/** Native Android host for the generated, C-only PEACOCK program. */
public final class MainActivity extends Activity {
    static { System.loadLibrary("peacock_program"); }

    private TextView output;
    private volatile boolean running;

    private synchronized native byte[] runPeacock();

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout column = new LinearLayout(this);
        column.setOrientation(LinearLayout.VERTICAL);
        Button run = new Button(this);
        run.setText("सूत्रं चालय");
        output = new TextView(this);
        output.setTypeface(Typeface.MONOSPACE);
        output.setTextIsSelectable(true);
        output.setPadding(24, 24, 24, 24);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(output);
        column.addView(run);
        column.addView(scroll);
        setContentView(column);
        run.setOnClickListener(view -> execute());
        execute();
    }

    private void execute() {
        if (running) return;
        running = true;
        output.setText("चलति…");
        new Thread(() -> {
            String text = new String(runPeacock(), StandardCharsets.UTF_8);
            runOnUiThread(() -> { output.setText(text); running = false; });
        }, "peacock-vm").start();
    }
}
