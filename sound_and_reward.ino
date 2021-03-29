String datafromUser= "5000,";
float intdata = 5000;
void setup() {
  // put your setup code here, to run once:
  pinMode( 7 , OUTPUT );
  pinMode(6, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  // put your main code here, to run repeatedly:
    if(Serial.available()>0){
    datafromUser=Serial.readStringUntil(',');
    intdata = datafromUser.toFloat();
    Serial.println(intdata);
       if(intdata == 314159265354 )
      {
        digitalWrite(6, HIGH);
        delay(300);
        digitalWrite(6, LOW);
        delay(5000);
        Serial.print("ok,");
       }
     }
     else{
      digitalWrite(7, HIGH);
      delayMicroseconds(intdata);
      digitalWrite(7, LOW);
      delayMicroseconds(intdata);
     }    
}
