'<ADbasic Header, Headerversion 001.001>
' Process_Number                 = 7
' Initial_Processdelay           = 2000
' Eventsource                    = Timer
' Control_long_Delays_for_Stop   = No
' Priority                       = Low
' Priority_Low_Level             = 1
' Version                        = 1
' ADbasic_Version                = 6.2.0
' Optimize                       = Yes
' Optimize_Level                 = 2
' Stacksize                      = 1000
' Info_Last_Save                 = PC-MINFLUX  PC-MINFLUX\USUARIO
'<Header End>
'process 7: Shutter control 

'README:
'Created by Lars Richter (Oct 2019)
'ADwin process to control state of up to six MediaLas shutters

'par_53: Shutter number (0 ... 5)
'par_52: Shutter state (0 - Closed, x - Open)


#INCLUDE .\data-acquisition.inc

dim flag as long at dm_local

INIT:
 
  Rem Configure DIO00.DIO15 as inputs and DIO16.DIO31 as outputs
  Conf_DIO(1100b)

EVENT:
    
  'Evaluate par_51 and select shutter accordingly
  SelectCase par_53
    Case 0 'Shutter 1 at port 18
      If (par_52 = 0) Then
        Digout(18, 0) 'Set TTL value to LOW
      Else
        Digout(18, 1) 'Set TTL value to HIGH
      EndIf
                      
    Case 1 'Shutter 2 at port 19
      If (par_52 = 0) Then
        Digout(19, 0) 'Set TTL value to LOW
      Else
        Digout(19, 1) 'Set TTL value to HIGH
      EndIf
                      
    Case 2 'Shutter 3 at port 20
      If (par_52 = 0) Then
        Digout(20, 0) 'Set TTL value to LOW
      Else
        Digout(20, 1) 'Set TTL value to HIGH
      EndIf
                      
    Case 3 'Shutter 4 at port 21
      If (par_52 = 0) Then
        Digout(21, 0) 'Set TTL value to LOW
      Else
        Digout(21, 1) 'Set TTL value to HIGH
      EndIf
                      
    Case 4 'Shutter 5 at port 22
      If (par_52 = 0) Then
        Digout(22, 0) 'Set TTL value to LOW
      Else
        Digout(22, 1) 'Set TTL value to HIGH
      EndIf     
                                                     
    Case 5 'Shutter 6 at port 23
      If (par_52 = 0) Then
        Digout(23, 0) 'Set TTL value to LOW
      Else
        Digout(23, 1) 'Set TTL value to HIGH
      EndIf
                      
    CaseElse
      flag = 0
                  
  EndSelect     
  
FINISH:
  