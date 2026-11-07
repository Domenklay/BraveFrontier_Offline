package com.domenklay.bravefrontieroffline;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;
import android.widget.Toast;
import org.json.JSONObject;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.function.Consumer;

/** Original offline prototype: no external assets, servers or network permissions. */
public final class MainActivity extends Activity {
    private static final int BG=Color.rgb(15,19,29);
    private static final int PANEL=Color.rgb(31,38,53);
    private static final int GOLD=Color.rgb(233,189,107);
    private static final int LIGHT=Color.rgb(240,234,218);
    private static final int MUTED=Color.rgb(162,172,187);
    private static final int IMPORT=601, EXPORT=602;
    private GameData data;
    private Battle battle;
    private LinearLayout body;
    private String page="home";

    @Override public void onCreate(Bundle state){
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        try{
            data=new GameData(this);
            battle=Battle.restore(data,data.savedBattle());
        }catch(Exception e){
            new AlertDialog.Builder(this).setTitle("Ошибка данных")
                    .setMessage(e.getMessage()).setPositiveButton("Закрыть",(d,w)->finish()).show();
            return;
        }
        render();
    }
    private int dp(float n){return Math.round(getResources().getDisplayMetrics().density*n);}
    private GradientDrawable shape(int color,int stroke){
        GradientDrawable d=new GradientDrawable();
        d.setColor(color);d.setCornerRadius(dp(13));
        d.setStroke(dp(1),stroke);return d;
    }
    private LinearLayout vertical(){
        LinearLayout l=new LinearLayout(this);
        l.setOrientation(LinearLayout.VERTICAL);
        return l;
    }
    private TextView text(String s,int sp,int color,boolean bold){
        TextView v=new TextView(this);
        v.setText(s);v.setTextSize(sp);v.setTextColor(color);
        if(bold)v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        v.setPadding(dp(2),dp(4),dp(2),dp(4));
        return v;
    }
    private void gap(LinearLayout l,int h){
        View v=new View(this);l.addView(v,new LinearLayout.LayoutParams(1,dp(h)));
    }
    private LinearLayout card(){
        LinearLayout l=vertical();
        l.setPadding(dp(15),dp(13),dp(15),dp(13));
        l.setBackground(shape(PANEL,Color.rgb(58,66,81)));
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);
        p.bottomMargin=dp(10);body.addView(l,p);
        return l;
    }
    private Button button(String label,Runnable action){
        Button b=new Button(this);
        b.setText(label);b.setTextSize(13);b.setAllCaps(false);b.setTextColor(LIGHT);
        b.setBackground(shape(Color.rgb(69,53,46),Color.rgb(157,113,67)));
        b.setOnClickListener(v->action.run());
        return b;
    }
    private void putButton(LinearLayout panel,String label,Runnable action){
        Button b=button(label,action);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,dp(47));
        p.topMargin=dp(6);panel.addView(b,p);
    }
    private void render(){
        LinearLayout root=vertical();
        root.setBackgroundColor(BG);
        root.setFitsSystemWindows(true);
        setContentView(root);

        LinearLayout head=vertical();
        head.setPadding(dp(17),dp(15),dp(17),dp(12));
        head.setBackgroundColor(Color.rgb(24,29,41));
        head.addView(text("BRAVE FRONTIER  /  OFFLINE",19,GOLD,true));
        head.addView(text("Прототип 0.1   •   Без сервера   •   Без интернета",11,MUTED,false));
        root.addView(head,new LinearLayout.LayoutParams(-1,-2));

        ScrollView scroller=new ScrollView(this);
        scroller.setFillViewport(true);
        body=vertical();
        body.setPadding(dp(14),dp(13),dp(14),dp(12));
        scroller.addView(body);
        root.addView(scroller,new LinearLayout.LayoutParams(-1,0,1));

        if("squad".equals(page))renderSquad();
        else if("battle".equals(page))renderBattle();
        else if("editor".equals(page))renderEditor();
        else renderHome();

        LinearLayout navigation=new LinearLayout(this);
        navigation.setPadding(dp(6),dp(5),dp(6),dp(5));
        navigation.setBackgroundColor(Color.rgb(25,30,43));
        nav(navigation,"Главная","home");
        nav(navigation,"Отряд","squad");
        nav(navigation,"Бой","battle");
        nav(navigation,"Редактор","editor");
        root.addView(navigation,new LinearLayout.LayoutParams(-1,dp(61)));
    }
    private void nav(LinearLayout row,String label,String destination){
        Button b=button(label,()->{page=destination;render();});
        b.setTextSize(12);
        if(page.equals(destination))b.setTextColor(GOLD);
        LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-1,1);
        p.leftMargin=dp(2);p.rightMargin=dp(2);
        row.addView(b,p);
    }
    private void renderHome(){
        LinearLayout summary=card();
        summary.addView(text("Книга призывателя",21,GOLD,true));
        summary.addView(text("Побед: "+data.victories()+"    •    Золото: "+data.gold(),15,LIGHT,true));
        summary.addView(text("Все данные хранятся в памяти этого телефона. Игра не запрашивает доступ к сети.",12,MUTED,false));
        if(battle!=null&&!battle.finished){
            putButton(summary,"Продолжить сохранённый бой",()->{page="battle";render();});
        }
        TextView cap=text("ДОСТУПНЫЕ РЕЖИМЫ",13,MUTED,true);
        body.addView(cap);
        for(GameData.Mode m:data.modes){
            LinearLayout panel=card();
            panel.addView(text(m.name,17,GOLD,true));
            panel.addView(text(m.description,13,LIGHT,false));
            panel.addView(text("Волн: "+m.waves+"  •  Награда: "+m.reward+"  •  Элемент: "+m.element,12,MUTED,false));
            putButton(panel,"Начать",()->startMode(m));
        }
        body.addView(text("Оригинальные ресурсы Brave Frontier в эту сборку не включены.",12,MUTED,false));
    }
    private void startMode(GameData.Mode m){
        if(battle!=null&&!battle.finished){
            new AlertDialog.Builder(this).setTitle("Незавершённый бой")
                    .setMessage("Начало нового похода заменит текущий сохранённый бой.")
                    .setNegativeButton("Отмена",null)
                    .setPositiveButton("Начать",(d,w)->doStartMode(m)).show();
        }else doStartMode(m);
    }
    private void doStartMode(GameData.Mode m){
        battle=new Battle(data,m);
        data.saveBattle(battle);
        page="battle";render();
    }
    private void renderSquad(){
        LinearLayout top=card();
        top.addView(text("Формирование отряда",21,GOLD,true));
        top.addView(text("Шесть героев. Нажмите на слот, чтобы заменить его. Изменения действуют со следующего похода.",12,MUTED,false));
        List<GameData.Unit> chosen=data.squad();
        for(int i=0;i<chosen.size();i++){
            final int slot=i;
            GameData.Unit u=chosen.get(i);
            LinearLayout p=card();
            p.addView(text((i+1)+". "+u.name+"  ["+u.element+"]",15,LIGHT,true));
            p.addView(text("HP "+u.hp+"    ATK "+u.atk+"    DEF "+u.def,12,MUTED,false));
            putButton(p,"Заменить",()->selectUnit(slot));
        }
    }
    private void selectUnit(int slot){
        String[] labels=new String[data.units.size()];
        for(int i=0;i<labels.length;i++){
            GameData.Unit u=data.units.get(i);
            labels[i]=u.name+"  ["+u.element+"]";
        }
        new AlertDialog.Builder(this).setTitle("Слот "+(slot+1))
                .setItems(labels,(d,which)->{
                    try{data.selectUnit(slot,data.units.get(which).id);render();}
                    catch(Exception e){error(e.getMessage());}
                }).show();
    }
    private void renderBattle(){
        if(battle==null){
            LinearLayout p=card();
            p.addView(text("Нет активного боя",20,GOLD,true));
            p.addView(text("Выберите режим на главной странице.",13,MUTED,false));
            putButton(p,"Выбрать режим",()->{page="home";render();});
            return;
        }
        LinearLayout info=card();
        info.addView(text(battle.mode.name,18,GOLD,true));
        info.addView(text("Волна "+battle.wave+"/"+battle.mode.waves+"     Ход "+battle.turn,13,LIGHT,true));
        info.addView(text("Противник: "+Math.max(0,battle.enemyHp)+"/"+battle.enemyMax+" HP  ["+battle.enemyElement()+"]",13,MUTED,false));
        BattleBoard board=new BattleBoard();
        info.addView(board,new LinearLayout.LayoutParams(-1,dp(226)));
        info.addView(text(battle.log,13,LIGHT,false));
        if(battle.finished){
            info.addView(text(battle.won?"ПОБЕДА":"ПОРАЖЕНИЕ",21,battle.won?GOLD:Color.rgb(241,118,116),true));
            putButton(info,"Повторить поход",()->startMode(battle.mode));
            putButton(info,"На главную",()->{page="home";render();});
            return;
        }
        body.addView(text("ВЫБЕРИТЕ ДЕЙСТВИЕ ГЕРОЯ",13,MUTED,true));
        for(int i=0;i<6;i++){
            final int index=i;
            GameData.Unit u=battle.squad[i];
            LinearLayout p=card();
            int hp=battle.hp[i];
            p.addView(text(u.name+"  ["+u.element+"]",14,GOLD,true));
            p.addView(text("HP "+hp+"/"+u.hp+"    BB "+battle.bb[i]+"/100"+(battle.acted[i]?"    •    Действовал":""),12,LIGHT,false));
            LinearLayout actions=new LinearLayout(this);
            Button attack=button("Атака",()->hit(index,false));
            attack.setEnabled(battle.canAct(i));
            actions.addView(attack,new LinearLayout.LayoutParams(0,dp(44),1));
            Button burst=button("Brave Burst",()->hit(index,true));
            burst.setEnabled(battle.canBurst(i));
            LinearLayout.LayoutParams b=new LinearLayout.LayoutParams(0,dp(44),1);
            b.leftMargin=dp(8);actions.addView(burst,b);
            p.addView(actions);
        }
        LinearLayout quit=card();
        putButton(quit,"Прервать поход",()->new AlertDialog.Builder(this)
                .setMessage("Потерять прогресс текущего похода?")
                .setNegativeButton("Нет",null)
                .setPositiveButton("Да",(d,w)->{battle=null;data.saveBattle(null);page="home";render();}).show());
    }
    private void hit(int index,boolean burst){
        if(battle==null)return;
        battle.attack(index,burst);
        if(battle.justWon){
            data.reward(battle.mode.reward);
            Toast.makeText(this,"Получено золото: "+battle.mode.reward,Toast.LENGTH_SHORT).show();
        }
        data.saveBattle(battle);
        render();
    }
    private static int elementColor(String e){
        switch(e){
            case "fire":return Color.rgb(226,105,77);
            case "water":return Color.rgb(82,167,228);
            case "earth":return Color.rgb(117,195,112);
            case "thunder":return Color.rgb(231,197,74);
            case "light":return Color.rgb(236,220,160);
            default:return Color.rgb(173,112,204);
        }
    }
    private class BattleBoard extends View {
        private final Paint p=new Paint(Paint.ANTI_ALIAS_FLAG);
        BattleBoard(){super(MainActivity.this);}
        @Override protected void onDraw(Canvas c){
            super.onDraw(c);
            if(battle==null)return;
            float w=getWidth(),h=getHeight();
            p.setColor(Color.rgb(18,27,43));
            c.drawRoundRect(new RectF(0,0,w,h),dp(11),dp(11),p);
            p.setColor(Color.rgb(77,57,64));
            c.drawRoundRect(new RectF(dp(9),dp(8),w-dp(9),h*0.45f),dp(11),dp(11),p);
            p.setColor(elementColor(battle.enemyElement()));
            c.drawCircle(w*.5f,h*.24f,dp(34),p);
            p.setColor(Color.rgb(255,240,220));
            p.setTextSize(dp(18));p.setTextAlign(Paint.Align.CENTER);
            c.drawText("✦",w*.5f,h*.27f,p);
            p.setTextSize(dp(11));
            c.drawText("ВРАГ",w*.5f,h*.44f,p);
            for(int i=0;i<6;i++){
                int col=i%3,row=i/3;
                float x=w*(col+0.5f)/3f;
                float y=h*(row==0?.64f:.85f);
                p.setColor(battle.hp[i]==0?Color.DKGRAY:elementColor(battle.squad[i].element));
                c.drawCircle(x,y,dp(20),p);
                p.setColor(Color.BLACK);p.setTextSize(dp(13));
                c.drawText(""+(i+1),x,y+dp(5),p);
                p.setColor(Color.rgb(70,76,88));
                c.drawRoundRect(new RectF(x-dp(30),y+dp(24),x+dp(30),y+dp(29)),dp(3),dp(3),p);
                p.setColor(Color.rgb(103,211,123));
                float ratio=(float)battle.hp[i]/battle.squad[i].hp;
                c.drawRoundRect(new RectF(x-dp(30),y+dp(24),x-dp(30)+dp(60)*ratio,y+dp(29)),dp(3),dp(3),p);
            }
        }
    }
    private void renderEditor(){
        LinearLayout p=card();
        p.addView(text("Редактор контента",21,GOLD,true));
        p.addView(text("Существа: "+data.units.size()+"  •  Режимы: "+data.modes.size(),14,LIGHT,true));
        p.addView(text("Создавайте собственных героев и подземелья. Данные и импортируемые JSON сохраняются локально.",12,MUTED,false));
        putButton(p,"Создать существо",this::newUnit);
        putButton(p,"Создать режим",this::newMode);
        putButton(p,"Импорт JSON-файла",this::importJson);
        putButton(p,"Экспорт собственных дополнений",this::exportJson);
        LinearLayout units=card();
        units.addView(text("КАТАЛОГ СУЩЕСТВ",14,GOLD,true));
        for(GameData.Unit u:data.units)units.addView(text(u.name+"   •   "+u.element+"   •   "+u.hp+" HP",12,LIGHT,false));
        LinearLayout modes=card();
        modes.addView(text("КАТАЛОГ РЕЖИМОВ",14,GOLD,true));
        for(GameData.Mode m:data.modes)modes.addView(text(m.name+"   •   "+m.waves+" волн",12,LIGHT,false));
    }
    private void inputDialog(String title,String[] fields,String[] defaults,Consumer<String[]> onSave){
        ScrollView scroller=new ScrollView(this);
        LinearLayout form=vertical();form.setPadding(dp(19),dp(10),dp(19),dp(10));
        EditText[] inputs=new EditText[fields.length];
        for(int i=0;i<fields.length;i++){
            form.addView(text(fields[i],12,Color.DKGRAY,true));
            EditText input=new EditText(this);
            input.setSingleLine(true);
            input.setText(defaults[i]);
            if(fields[i].startsWith("#"))input.setInputType(InputType.TYPE_CLASS_NUMBER);
            form.addView(input,new LinearLayout.LayoutParams(-1,dp(53)));
            inputs[i]=input;
        }
        scroller.addView(form);
        new AlertDialog.Builder(this).setTitle(title).setView(scroller)
                .setNegativeButton("Отмена",null)
                .setPositiveButton("Сохранить",(d,w)->{
                    String[] values=new String[inputs.length];
                    for(int i=0;i<inputs.length;i++)values[i]=inputs[i].getText().toString().trim();
                    try{onSave.accept(values);render();}
                    catch(Exception e){error(e.getMessage());}
                }).show();
    }
    private void newUnit(){
        inputDialog("Новое существо",new String[]{"ID (латиницей)","Имя","Элемент (fire/water/earth/thunder/light/dark)","# HP","# ATK","# DEF"},
                new String[]{"hero_"+System.currentTimeMillis()%1000000,"Новый герой","fire","200","65","20"},values->{
                    try{
                        JSONObject j=new JSONObject().put("id",values[0]).put("name",values[1])
                                .put("element",values[2]).put("hp",Integer.parseInt(values[3]))
                                .put("atk",Integer.parseInt(values[4])).put("def",Integer.parseInt(values[5]));
                        data.addUnit(GameData.Unit.parse(j));
                        Toast.makeText(this,"Герой добавлен",Toast.LENGTH_SHORT).show();
                    }catch(Exception e){error(e.getMessage());}
                });
    }
    private void newMode(){
        inputDialog("Новый режим",new String[]{"ID (латиницей)","Название","Описание","# Волн","# HP врага","# ATK врага","Элемент (fire/water/earth/thunder/light/dark)","# Награда"},
                new String[]{"stage_"+System.currentTimeMillis()%1000000,"Новое подземелье","Создано игроком","3","300","40","dark","180"},values->{
                    try{
                        JSONObject j=new JSONObject().put("id",values[0]).put("name",values[1])
                                .put("description",values[2]).put("waves",Integer.parseInt(values[3]))
                                .put("enemyHp",Integer.parseInt(values[4])).put("enemyAtk",Integer.parseInt(values[5]))
                                .put("element",values[6]).put("reward",Integer.parseInt(values[7]));
                        data.addMode(GameData.Mode.parse(j));
                        Toast.makeText(this,"Режим добавлен",Toast.LENGTH_SHORT).show();
                    }catch(Exception e){error(e.getMessage());}
                });
    }
    private void importJson(){
        Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("*/*");
        startActivityForResult(i,IMPORT);
    }
    private void exportJson(){
        Intent i=new Intent(Intent.ACTION_CREATE_DOCUMENT);
        i.addCategory(Intent.CATEGORY_OPENABLE);
        i.setType("application/json");
        i.putExtra(Intent.EXTRA_TITLE,"bf-offline-custom.json");
        startActivityForResult(i,EXPORT);
    }
    @Override protected void onActivityResult(int request,int result,Intent intent){
        super.onActivityResult(request,result,intent);
        if(result!=RESULT_OK||intent==null||intent.getData()==null||data==null)return;
        try{
            if(request==IMPORT){
                ByteArrayOutputStream bytes=new ByteArrayOutputStream();
                try(InputStream stream=getContentResolver().openInputStream(intent.getData())){
                    if(stream==null)throw new Exception("Unable to read file");
                    byte[] buffer=new byte[8192];int n;
                    while((n=stream.read(buffer))!=-1){
                        if(bytes.size()+n>1024*1024)throw new Exception("JSON pack exceeds 1 MB");
                        bytes.write(buffer,0,n);
                    }
                }
                int count=data.importPack(new String(bytes.toByteArray(),StandardCharsets.UTF_8));
                Toast.makeText(this,"Импортировано: "+count,Toast.LENGTH_LONG).show();
            }else if(request==EXPORT){
                try(OutputStream out=getContentResolver().openOutputStream(intent.getData())){
                    if(out==null)throw new Exception("Unable to write file");
                    out.write(data.exportCustom().getBytes(StandardCharsets.UTF_8));
                }
                Toast.makeText(this,"Пакет сохранён",Toast.LENGTH_SHORT).show();
            }
            render();
        }catch(Exception e){error(e.getMessage());}
    }
    private void error(String message){
        new AlertDialog.Builder(this).setTitle("Ошибка").setMessage(message)
                .setPositiveButton("Понятно",null).show();
    }
}
